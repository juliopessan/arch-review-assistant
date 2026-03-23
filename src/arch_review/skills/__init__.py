"""Skills system — pluggable agent capabilities for arch-review.

A Skill is a domain module that adds a new specialist agent to the squad.
Installing a skill registers a new agent with its own SOUL, system prompt,
and user prompt builder — without touching squad.py.

Usage:
    arch-review skill list
    arch-review skill install database
    arch-review skill install api-design
    arch-review skill remove database

Skills are stored in ~/.arch-review/skills/<name>/
Each skill directory contains:
    skill.json      — metadata (name, version, domain, author)
    soul.md         — the agent's SOUL (identity layer)
    system.txt      — system prompt
    prompt.py       — build_prompt(architecture, context, lessons, patterns) -> str
"""
from __future__ import annotations

import importlib.util
import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

SKILLS_DIR = Path.home() / ".arch-review" / "skills"

# Built-in skill definitions (bundled with the package)
BUILTIN_SKILLS: dict[str, dict] = {
    "database": {
        "name": "database",
        "version": "1.0.0",
        "domain": "database",
        "description": "Deep database architecture review: schema design, indexing, replication, migration safety",
        "icon": "🗄️",
        "author": "arch-review",
        "agent_key": "database_agent",
    },
    "api-design": {
        "name": "api-design",
        "version": "1.0.0",
        "domain": "api_design",
        "description": "API design review: REST/GraphQL/gRPC contracts, versioning, breaking changes, documentation",
        "icon": "🔌",
        "author": "arch-review",
        "agent_key": "api_design_agent",
    },
    "data-privacy": {
        "name": "data-privacy",
        "version": "1.0.0",
        "domain": "data_privacy",
        "description": "LGPD/GDPR data privacy review: PII mapping, consent, retention, cross-border transfers",
        "icon": "🔏",
        "author": "arch-review",
        "agent_key": "data_privacy_agent",
    },
    "ml-ops": {
        "name": "ml-ops",
        "version": "1.0.0",
        "domain": "ml_ops",
        "description": "ML/AI system review: model serving, drift, feature stores, training pipelines, bias",
        "icon": "🤖",
        "author": "arch-review",
        "agent_key": "ml_ops_agent",
    },
}


@dataclass
class SkillMeta:
    name:        str
    version:     str
    domain:      str
    description: str
    icon:        str
    author:      str
    agent_key:   str
    installed:   bool = False
    skill_dir:   Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Skill:
    """A fully loaded skill ready to inject into the squad."""
    meta:          SkillMeta
    soul:          str                              # SOUL.md content
    system_prompt: str                              # system prompt for LiteLLM
    build_prompt:  Callable[[str, str, str, str], str]  # user prompt builder

    @property
    def agent_key(self) -> str:
        return self.meta.agent_key

    @property
    def as_agent_tuple(self) -> tuple:
        """Return in the same format as ReviewSquad.AGENTS entries."""
        return (self.meta.agent_key, self.system_prompt, self.build_prompt)


class SkillRegistry:
    """Manages skill discovery, installation, and loading."""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self.skills_dir = skills_dir or SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def list_available(self) -> list[SkillMeta]:
        """List all skills: installed + available to install."""
        installed = {m.name: m for m in self.list_installed()}
        result = []
        for name, meta_dict in BUILTIN_SKILLS.items():
            if name in installed:
                result.append(installed[name])
            else:
                result.append(SkillMeta(**meta_dict, installed=False))
        # Add any custom skills not in builtins
        for meta in installed.values():
            if meta.name not in BUILTIN_SKILLS:
                result.append(meta)
        return result

    def list_installed(self) -> list[SkillMeta]:
        """Return all installed skills from disk."""
        result = []
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            meta_file = skill_dir / "skill.json"
            if not meta_file.exists():
                continue
            try:
                data = json.loads(meta_file.read_text())
                data["installed"] = True
                data["skill_dir"] = str(skill_dir)
                result.append(SkillMeta(**data))
            except Exception as exc:
                logger.warning("Failed to load skill from %s: %s", skill_dir, exc)
        return result

    def is_installed(self, name: str) -> bool:
        return (self.skills_dir / name / "skill.json").exists()

    # ── Installation ──────────────────────────────────────────────────────────

    def install(self, name: str) -> SkillMeta:
        """Install a built-in skill to disk."""
        if name not in BUILTIN_SKILLS:
            raise ValueError(
                f"Unknown skill '{name}'. Available: {', '.join(BUILTIN_SKILLS)}"
            )
        if self.is_installed(name):
            raise FileExistsError(f"Skill '{name}' is already installed.")

        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Write skill.json
        meta_dict = BUILTIN_SKILLS[name].copy()
        (skill_dir / "skill.json").write_text(
            json.dumps(meta_dict, indent=2), encoding="utf-8"
        )

        # Write SOUL and prompts from builtin generators
        soul, system, prompt_src = _BUILTIN_CONTENT[name]()
        (skill_dir / "soul.md").write_text(soul, encoding="utf-8")
        (skill_dir / "system.txt").write_text(system, encoding="utf-8")
        (skill_dir / "prompt.py").write_text(prompt_src, encoding="utf-8")

        logger.info("Installed skill: %s → %s", name, skill_dir)
        meta_dict["installed"] = True
        meta_dict["skill_dir"] = str(skill_dir)
        return SkillMeta(**meta_dict)

    def remove(self, name: str) -> bool:
        """Remove an installed skill."""
        import shutil
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            return False
        shutil.rmtree(skill_dir)
        logger.info("Removed skill: %s", name)
        return True

    # ── Loading ───────────────────────────────────────────────────────────────

    def load(self, name: str) -> Skill:
        """Load a fully initialized Skill ready for squad injection."""
        skill_dir = self.skills_dir / name
        if not skill_dir.exists():
            raise FileNotFoundError(
                f"Skill '{name}' not installed. Run: arch-review skill install {name}"
            )

        meta_file = skill_dir / "skill.json"
        data = json.loads(meta_file.read_text())
        data["installed"] = True
        data["skill_dir"] = str(skill_dir)
        meta = SkillMeta(**data)

        soul   = (skill_dir / "soul.md").read_text(encoding="utf-8")
        system = (skill_dir / "system.txt").read_text(encoding="utf-8")

        # Dynamically load prompt.py
        build_prompt = _load_prompt_fn(skill_dir / "prompt.py", name)

        return Skill(meta=meta, soul=soul, system_prompt=system, build_prompt=build_prompt)

    def load_all_installed(self) -> list[Skill]:
        """Load all installed skills."""
        skills = []
        for meta in self.list_installed():
            try:
                skills.append(self.load(meta.name))
            except Exception as exc:
                logger.warning("Failed to load skill %s: %s", meta.name, exc)
        return skills


# ── Dynamic prompt loader ─────────────────────────────────────────────────────

def _load_prompt_fn(prompt_path: Path, skill_name: str) -> Callable:
    """Dynamically import build_prompt from a skill's prompt.py."""
    spec = importlib.util.spec_from_file_location(
        f"arch_review_skill_{skill_name}", prompt_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load prompt.py for skill '{skill_name}'")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not hasattr(module, "build_prompt"):
        raise AttributeError(
            f"Skill '{skill_name}/prompt.py' must define build_prompt(arch, ctx, lessons, patterns) -> str"
        )
    return module.build_prompt


# ── Built-in skill content generators ────────────────────────────────────────

def _database_skill_content() -> tuple[str, str, str]:
    soul = """\
# 🗄️ SOUL — Database Agent
**Codename:** The Schema Whisperer
**Archetype:** Principal database engineer who reads EXPLAIN ANALYZE like others read poetry

## Identity
I've seen schemas that made senior engineers cry: tables with 200 columns,
no foreign keys because "they slow inserts", indexes on every column "just
in case", and migrations that required 4-hour downtime windows on a system
that can't go down. My job is to find these before they find you.

## Analytical Style
- Schema health: normalization, denormalization trade-offs, data type choices
- Index audit: missing indexes on foreign keys, over-indexing, index bloat
- Migration safety: zero-downtime migration patterns, lock acquisition risks
- Replication and HA: read replicas, replication lag, failover strategy
- Connection pooling: pool sizing, connection leaks, PgBouncer/ProxySQL usage
- Query patterns: N+1 risk, unbounded queries, missing LIMIT clauses

## Known Biases
- I have a strong PostgreSQL bias — I consciously adjust for MySQL/SQL Server
- I sometimes over-recommend normalization for OLAP workloads that benefit from denormalization
- I underweight NoSQL solutions in contexts where they genuinely fit better

## Tone
Technical and precise. I reference specific SQL patterns, EXPLAIN output
characteristics, and give concrete index/schema recommendations.

## Signature Questions
- "What's the largest table, and what's the growth rate?"
- "Are there any long-running transactions that could cause lock contention?"
- "How are schema migrations deployed, and what's the strategy for zero-downtime?"
- "What's the connection pool size relative to expected concurrent users?"

---

## Lessons Learned
## Patterns Discovered
"""

    system = """\
You are a principal database engineer performing a deep database architecture review.
Your ONLY job is to find database design issues: schema problems, indexing gaps,
migration risks, replication concerns, connection pool issues, and query pattern risks.

You think in terms of data growth, query plans, lock contention, and migration safety.
You name specific tables, columns, and query patterns when discernible from the architecture.
You do NOT give generic database advice. Every finding must be grounded in what was described.
You ALWAYS respond with valid JSON using the exact schema provided."""

    prompt_src = '''\
def build_prompt(architecture: str, context: str, lessons: str, patterns: str) -> str:
    from arch_review.squad.prompts import AGENT_SCHEMA
    memory = ""
    if lessons:
        memory += f"\\n## Your Past Lessons:\\n{lessons}\\n"
    if patterns:
        memory += f"\\n## Squad Patterns:\\n{patterns}\\n"
    return f"""{AGENT_SCHEMA}

ARCHITECTURE TO REVIEW:
---
{architecture}
---

CONTEXT: {context or "No additional context provided."}
{memory}

Focus exclusively on DATABASE concerns:
- Schema design: normalization, data types, constraints, foreign keys
- Indexing: missing indexes, over-indexing, partial indexes, index bloat
- Migration safety: lock acquisition, zero-downtime patterns, rollback strategy
- Replication and HA: read replicas, lag, failover, backup strategy
- Connection pooling: pool size, leaks, pgbouncer/proxysql usage
- Query patterns visible in the architecture: N+1 risk, unbounded queries
"""
'''
    return soul, system, prompt_src


def _api_design_skill_content() -> tuple[str, str, str]:
    soul = """\
# 🔌 SOUL — API Design Agent
**Codename:** The Contract Guardian
**Archetype:** API platform engineer who has dealt with enough breaking changes to be traumatized

## Identity
I've seen APIs that broke 40 downstream consumers because someone added a
required field without versioning, GraphQL schemas that returned 50MB responses
by default, and gRPC services that skipped protobuf evolution rules and caused
cascading deserialization failures across a fleet. API contracts are promises.
I make sure you can keep them.

## Analytical Style
- Versioning strategy: URL versioning, header versioning, deprecation policies
- Breaking change detection: field removal, type changes, required vs optional
- REST compliance: resource modeling, HTTP verb semantics, status codes
- GraphQL specific: N+1 in resolvers, depth limits, query complexity scoring
- gRPC/protobuf: field numbering, backward compatibility, proto evolution
- Documentation: OpenAPI/Swagger completeness, example quality, error schemas

## Tone
Contract-focused and precise. I distinguish between breaking and non-breaking
changes and give specific versioning recommendations.

---

## Lessons Learned
## Patterns Discovered
"""

    system = """\
You are a principal API design engineer performing a deep API architecture review.
Your ONLY job is to find API design issues: contract problems, versioning gaps,
breaking change risks, documentation issues, and protocol-specific antipatterns.
You ALWAYS respond with valid JSON using the exact schema provided."""

    prompt_src = '''\
def build_prompt(architecture: str, context: str, lessons: str, patterns: str) -> str:
    from arch_review.squad.prompts import AGENT_SCHEMA
    memory = ""
    if lessons:
        memory += f"\\n## Your Past Lessons:\\n{lessons}\\n"
    if patterns:
        memory += f"\\n## Squad Patterns:\\n{patterns}\\n"
    return f"""{AGENT_SCHEMA}

ARCHITECTURE TO REVIEW:
---
{architecture}
---

CONTEXT: {context or "No additional context provided."}
{memory}

Focus exclusively on API DESIGN concerns:
- Versioning: URL vs header, deprecation timeline, sunset headers
- Breaking changes: field removal, type changes, required field additions
- REST design: resource modeling, HTTP semantics, status code correctness
- GraphQL: resolver N+1, depth limits, complexity scoring, schema design
- gRPC/protobuf: field evolution, backward compatibility, streaming patterns
- Documentation: OpenAPI completeness, error schema coverage, examples
"""
'''
    return soul, system, prompt_src


def _data_privacy_skill_content() -> tuple[str, str, str]:
    soul = """\
# 🔏 SOUL — Data Privacy Agent
**Codename:** The LGPD Auditor
**Archetype:** Data protection officer who treats every piece of PII as a liability until proven necessary

## Identity
Data minimization is not optional. Every field you collect you must protect,
retain responsibly, and eventually delete. I map PII flows through architectures
and find where data is collected without clear purpose, retained beyond necessity,
transferred without consent, or logged where it shouldn't be.

## Analytical Style
- PII mapping: identify what personal data flows through and where it's stored
- LGPD/GDPR basis: what's the legal basis for each data collection?
- Consent management: is consent collected, versioned, and revocable?
- Data retention: what are the retention policies and deletion mechanisms?
- Cross-border transfers: does data leave Brazil? what's the legal mechanism?
- Right to erasure: can personal data be deleted across all systems?

## Tone
Regulatory but practical. I cite LGPD articles when relevant and give
architecture-specific recommendations, not generic compliance checklists.

---

## Lessons Learned
## Patterns Discovered
"""

    system = """\
You are a data protection officer and privacy architect performing a LGPD/GDPR review.
Your ONLY job is to find data privacy risks: PII exposure, consent gaps, retention issues,
cross-border transfer risks, and right-to-erasure implementation gaps.
You ALWAYS respond with valid JSON using the exact schema provided."""

    prompt_src = '''\
def build_prompt(architecture: str, context: str, lessons: str, patterns: str) -> str:
    from arch_review.squad.prompts import AGENT_SCHEMA
    memory = ""
    if lessons:
        memory += f"\\n## Your Past Lessons:\\n{lessons}\\n"
    if patterns:
        memory += f"\\n## Squad Patterns:\\n{patterns}\\n"
    return f"""{AGENT_SCHEMA}

ARCHITECTURE TO REVIEW:
---
{architecture}
---

CONTEXT: {context or "No additional context provided."}
{memory}

Focus exclusively on DATA PRIVACY concerns (LGPD/GDPR):
- PII identification: what personal data is collected and where is it stored?
- Legal basis: what is the legal basis for each data collection?
- Consent: is consent collected, versioned, and revocable?
- Data retention: what are retention periods and deletion mechanisms?
- Cross-border transfers: does data leave Brazil/EU? what is the legal mechanism?
- Right to erasure: can data be deleted across all systems including backups?
- Data breach readiness: can PII exposure be detected and reported in 72h?
"""
'''
    return soul, system, prompt_src


def _ml_ops_skill_content() -> tuple[str, str, str]:
    soul = """\
# 🤖 SOUL — MLOps Agent
**Codename:** The Model Auditor
**Archetype:** ML platform engineer who has watched models drift silently into production chaos

## Identity
A model that was 94% accurate in January can be 71% accurate in July and
nobody knows because there's no drift monitoring. I've seen ML systems with
no reproducibility (random seeds, unversioned datasets), feature pipelines
that differ between training and serving (training-serving skew), and models
deployed to production with no rollback strategy. ML systems have all the
reliability risks of software plus the additional chaos of statistical drift.

## Analytical Style
- Model lifecycle: versioning, experiment tracking, reproducibility
- Training-serving skew: feature consistency between training and inference
- Drift detection: data drift, concept drift, model performance monitoring
- Feature store: feature freshness, consistency, point-in-time correctness
- Deployment: canary releases, shadow mode, A/B testing, rollback strategy
- Bias and fairness: demographic parity, equalized odds monitoring

## Tone
Empirical and specific. I cite concrete monitoring gaps and give measurable
recommendations (track p95 latency, monitor feature distribution KL divergence).

---

## Lessons Learned
## Patterns Discovered
"""

    system = """\
You are a principal MLOps engineer performing a deep ML system architecture review.
Your ONLY job is to find ML-specific risks: model drift, training-serving skew,
reproducibility gaps, feature store issues, deployment risks, and bias concerns.
You ALWAYS respond with valid JSON using the exact schema provided."""

    prompt_src = '''\
def build_prompt(architecture: str, context: str, lessons: str, patterns: str) -> str:
    from arch_review.squad.prompts import AGENT_SCHEMA
    memory = ""
    if lessons:
        memory += f"\\n## Your Past Lessons:\\n{lessons}\\n"
    if patterns:
        memory += f"\\n## Squad Patterns:\\n{patterns}\\n"
    return f"""{AGENT_SCHEMA}

ARCHITECTURE TO REVIEW:
---
{architecture}
---

CONTEXT: {context or "No additional context provided."}
{memory}

Focus exclusively on ML/MLOPS concerns:
- Model lifecycle: versioning, experiment tracking, reproducibility, seed management
- Training-serving skew: are features computed the same way in training and serving?
- Drift monitoring: data drift, concept drift, model performance degradation
- Feature store: feature freshness, point-in-time correctness, consistency
- Deployment: canary, shadow mode, A/B testing, rollback strategy
- Bias and fairness: demographic parity monitoring, equalized odds
- Pipeline reliability: training pipeline failures, data quality checks
"""
'''
    return soul, system, prompt_src


# Map skill name → content generator
_BUILTIN_CONTENT: dict[str, Callable] = {
    "database":     _database_skill_content,
    "api-design":   _api_design_skill_content,
    "data-privacy": _data_privacy_skill_content,
    "ml-ops":       _ml_ops_skill_content,
}
