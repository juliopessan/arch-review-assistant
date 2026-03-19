"""Agent Manager — pre-analyzes the architecture and orchestrates squad focus."""

from __future__ import annotations

from arch_review.models import AgentFocusPlan, ArchitectureInput, OrchestrationPlanSnapshot


class AgentManager:
    """Deterministic manager that plans which agents should focus on what."""

    AGENT_ORDER = [
        "security_agent",
        "reliability_agent",
        "cost_agent",
        "observability_agent",
    ]

    def create_plan(self, arch_input: ArchitectureInput) -> OrchestrationPlanSnapshot:
        """Analyze the input and produce an orchestration plan snapshot."""
        text = f"{arch_input.description}\n{arch_input.context or ''}".lower()

        architecture_type = self._classify_architecture(text)
        complexity = self._estimate_complexity(text)
        compliance_flags = self._find_compliance_flags(text)
        cloud_providers = self._find_cloud_providers(text)
        top_risks = self._find_top_risks(text)

        agent_plans = [
            self._plan_security(text, compliance_flags),
            self._plan_reliability(text),
            self._plan_cost(text, cloud_providers),
            self._plan_observability(text),
        ]

        return OrchestrationPlanSnapshot(
            architecture_type=architecture_type,
            complexity=complexity,
            compliance_flags=compliance_flags,
            cloud_providers=cloud_providers,
            top_risks=top_risks,
            manager_briefing=self._build_briefing(
                architecture_type=architecture_type,
                complexity=complexity,
                compliance_flags=compliance_flags,
                cloud_providers=cloud_providers,
                top_risks=top_risks,
                agent_plans=agent_plans,
            ),
            agent_plans=agent_plans,
        )

    def build_agent_guidance(self, plan: OrchestrationPlanSnapshot, agent_name: str) -> str:
        """Build prompt guidance for a single agent from the orchestration plan."""
        agent_plan = next((item for item in plan.agent_plans if item.agent_name == agent_name), None)
        if agent_plan is None:
            return ""

        guidance = [
            "## Agent Manager Briefing",
            f"- Architecture type: {plan.architecture_type}",
            f"- Estimated complexity: {plan.complexity}",
            f"- Priority for you: {agent_plan.priority}",
            f"- Active: {'yes' if agent_plan.active else 'no'}",
            f"- Why: {agent_plan.rationale}",
        ]

        if plan.compliance_flags:
            guidance.append(f"- Compliance flags: {', '.join(plan.compliance_flags)}")
        if plan.cloud_providers:
            guidance.append(f"- Cloud providers: {', '.join(plan.cloud_providers)}")
        if plan.top_risks:
            guidance.append(f"- Top pre-review risks: {', '.join(plan.top_risks)}")
        if agent_plan.focus_areas:
            guidance.append("- Your focus directives:")
            guidance.extend(f"  - {item}" for item in agent_plan.focus_areas)

        return "\n".join(guidance)

    def build_manager_lesson(self, plan: OrchestrationPlanSnapshot) -> str:
        """Summarize the orchestration decision as a memory lesson."""
        active_agents = [p.agent_name for p in plan.agent_plans if p.active]
        return (
            f"Classified {plan.architecture_type} architecture as {plan.complexity} complexity. "
            f"Prioritized {', '.join(active_agents)} based on risks: {', '.join(plan.top_risks[:3]) or 'general review'}."
        )

    def _classify_architecture(self, text: str) -> str:
        if any(token in text for token in ("event", "queue", "rabbitmq", "kafka", "pub/sub", "service bus")):
            return "event-driven distributed system"
        if any(token in text for token in ("microservice", "microservices", "api gateway")):
            return "microservices platform"
        if any(token in text for token in ("lambda", "serverless", "cloud function")):
            return "serverless architecture"
        if any(token in text for token in ("monolith", "single app", "single service")):
            return "monolith"
        return "service-oriented architecture"

    def _estimate_complexity(self, text: str) -> str:
        signals = sum(
            1
            for token in (
                "api gateway", "queue", "worker", "kafka", "rabbitmq", "service bus",
                "multi-region", "multi-az", "microservice", "microservices", "cdn",
                "redis", "postgres", "mysql", "observability", "tracing", "webhook",
            )
            if token in text
        )
        if signals >= 8:
            return "high"
        if signals >= 4:
            return "medium"
        return "low"

    def _find_compliance_flags(self, text: str) -> list[str]:
        matches = []
        mapping = {
            "lgpd": "LGPD",
            "gdpr": "GDPR",
            "hipaa": "HIPAA",
            "pci": "PCI-DSS",
            "soc 2": "SOC 2",
        }
        for token, label in mapping.items():
            if token in text:
                matches.append(label)
        return matches

    def _find_cloud_providers(self, text: str) -> list[str]:
        providers = []
        mapping = {
            "aws": ("aws", "ec2", "rds", "s3", "cloudwatch"),
            "azure": ("azure", "entra", "aks", "service bus"),
            "gcp": ("gcp", "google cloud", "bigquery", "cloud run", "gke"),
        }
        for label, tokens in mapping.items():
            if any(token in text for token in tokens):
                providers.append(label)
        return providers

    def _find_top_risks(self, text: str) -> list[str]:
        risk_rules = [
            ("single point of failure risk", ("single ec2", "single instance", "single postgres", "single database")),
            ("weak observability baseline", ("logs written to local files", "local log", "no tracing", "no metrics")),
            ("compliance-sensitive data handling", ("lgpd", "gdpr", "hipaa", "pii", "pci")),
            ("synchronous dependency chain", ("synchronous", "sync call", "stripe", "calls payment")),
            ("message durability and retry gaps", ("rabbitmq", "kafka", "queue", "retry", "dlq")),
        ]
        risks = [label for label, tokens in risk_rules if any(token in text for token in tokens)]
        return risks or ["cross-domain architecture review needed"]

    def _plan_security(self, text: str, compliance_flags: list[str]) -> AgentFocusPlan:
        focus = [
            "Inspect authentication, authorization, and service-to-service trust boundaries.",
            "Check secrets handling and exposure of data in transit or at rest.",
        ]
        priority = "critical" if compliance_flags or any(token in text for token in ("auth", "jwt", "oauth", "entra")) else "high"
        if compliance_flags:
            focus.append(f"Treat compliance as first-class: {', '.join(compliance_flags)}.")
        return AgentFocusPlan(
            agent_name="security_agent",
            priority=priority,
            active=True,
            rationale="Security is always active and becomes top priority when identity or compliance-sensitive data is present.",
            focus_areas=focus,
        )

    def _plan_reliability(self, text: str) -> AgentFocusPlan:
        high_priority = any(token in text for token in ("single", "queue", "kafka", "rabbitmq", "rds", "postgres", "payment"))
        focus = [
            "Map single points of failure and cascading dependency chains.",
            "Stress critical data stores, queues, and synchronous integrations.",
        ]
        return AgentFocusPlan(
            agent_name="reliability_agent",
            priority="high" if high_priority else "medium",
            active=True,
            rationale="Reliability is essential whenever stateful components or synchronous integrations appear.",
            focus_areas=focus,
        )

    def _plan_cost(self, text: str, cloud_providers: list[str]) -> AgentFocusPlan:
        cloud_heavy = bool(cloud_providers) or any(token in text for token in ("autoscaling", "cdn", "s3", "multi-az", "serverless"))
        clearly_non_cloud = any(token in text for token in ("on-prem", "on prem", "datacenter", "bare metal", "air-gapped"))
        focus = [
            "Look for structural cost drivers such as overprovisioning, cross-zone traffic, and self-hosted platform choices.",
        ]
        if any(token in text for token in ("single ec2", "single instance", "self-hosted", "rabbitmq on same")):
            focus.append("Compare self-hosted components against managed alternatives.")
        return AgentFocusPlan(
            agent_name="cost_agent",
            priority="medium" if cloud_heavy else "low",
            active=not clearly_non_cloud,
            rationale=(
                "Cost stays active when cloud or hosting decisions materially affect architecture trade-offs."
                if not clearly_non_cloud
                else "Cost was skipped because the description points to a clearly on-prem or air-gapped setup with limited cloud trade-off surface."
            ),
            focus_areas=focus,
        )

    def _plan_observability(self, text: str) -> AgentFocusPlan:
        weak_baseline = any(token in text for token in ("local log", "logs written to local files", "no tracing", "no metrics"))
        focus = [
            "Evaluate whether incidents can be diagnosed quickly across services and integrations.",
            "Check for logs, metrics, tracing, and operational readiness signals.",
        ]
        return AgentFocusPlan(
            agent_name="observability_agent",
            priority="high" if weak_baseline else "medium",
            active=True,
            rationale="Observability becomes urgent when logs are local or distributed tracing signals are absent.",
            focus_areas=focus,
        )

    def _build_briefing(
        self,
        architecture_type: str,
        complexity: str,
        compliance_flags: list[str],
        cloud_providers: list[str],
        top_risks: list[str],
        agent_plans: list[AgentFocusPlan],
    ) -> str:
        top_agent = max(
            agent_plans,
            key=lambda plan: {"critical": 3, "high": 2, "medium": 1, "low": 0}[plan.priority],
        )
        extras = []
        if compliance_flags:
            extras.append(f"compliance flags: {', '.join(compliance_flags)}")
        if cloud_providers:
            extras.append(f"cloud: {', '.join(cloud_providers)}")
        extra_clause = f" with {'; '.join(extras)}" if extras else ""
        return (
            f"Manager classified the input as a {complexity} {architecture_type}{extra_clause}. "
            f"Top pre-review risks: {', '.join(top_risks[:3])}. "
            f"Highest emphasis goes to {top_agent.agent_name}."
        )
