"""Agent Registry and Capability Registry for the multi-agent runtime.

The registry is the central catalogue of all agents available to the
supervisor.  It tracks each agent's role, capabilities, retry policy,
and inter-agent dependencies.  No business logic -- only bookkeeping.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.runtime.types import (
    AgentRegistration,
    AgentRole,
)


class AgentRegistry:
    """Registry of all agents available to the investigation runtime.

    Agents are registered at startup.  The supervisor queries this registry
    to discover which agents exist, what they can do, and how to invoke
    them safely.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentRegistration] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, registration: AgentRegistration) -> None:
        if registration.name in self._agents:
            raise ValueError(
                f"Agent '{registration.name}' is already registered. "
                "Unregister first or use a unique name."
            )
        self._agents[registration.name] = registration

    def unregister(self, name: str) -> AgentRegistration | None:
        return self._agents.pop(name, None)

    def is_registered(self, name: str) -> bool:
        return name in self._agents

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> AgentRegistration | None:
        return self._agents.get(name)

    def get_or_raise(self, name: str) -> AgentRegistration:
        reg = self._agents.get(name)
        if reg is None:
            raise KeyError(f"Agent '{name}' is not registered.")
        return reg

    def list_agents(self) -> list[AgentRegistration]:
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_by_role(self, role: AgentRole) -> list[AgentRegistration]:
        return [a for a in self._agents.values() if a.role == role]

    def get_parallel_capable(self) -> list[AgentRegistration]:
        return [a for a in self._agents.values() if a.can_run_in_parallel]

    def get_requiring_approval(self) -> list[AgentRegistration]:
        return [a for a in self._agents.values() if a.requires_human_approval]

    def get_by_capability(self, capability_name: str) -> list[AgentRegistration]:
        """Find agents that produce a given capability."""
        results: list[AgentRegistration] = []
        for reg in self._agents.values():
            for cap in reg.capabilities:
                if capability_name in cap.output_types:
                    results.append(reg)
                    break
        return results

    def get_consuming(self, capability_name: str) -> list[AgentRegistration]:
        """Find agents that consume a given capability."""
        results: list[AgentRegistration] = []
        for reg in self._agents.values():
            for cap in reg.capabilities:
                if capability_name in cap.input_types:
                    results.append(reg)
                    break
        return results

    def get_dependencies(self, agent_name: str) -> list[str]:
        """Return the names of agents that ``agent_name`` depends on."""
        reg = self._agents.get(agent_name)
        if reg is None:
            return []
        deps: list[str] = []
        for cap in reg.capabilities:
            deps.extend(cap.dependencies)
        return list(dict.fromkeys(deps))

    def get_dependents(self, agent_name: str) -> list[str]:
        """Return the names of agents that depend on ``agent_name``."""
        dependents: list[str] = []
        for name, reg in self._agents.items():
            if name == agent_name:
                continue
            for cap in reg.capabilities:
                if agent_name in cap.dependencies:
                    dependents.append(name)
                    break
        return dependents

    # ------------------------------------------------------------------
    # Parallel execution groups
    # ------------------------------------------------------------------

    def get_executable_agents(
        self, completed: list[str], pending: list[str]
    ) -> list[AgentRegistration]:
        """Return agents whose dependencies are all satisfied and that
        are not yet completed or pending."""
        executable: list[AgentRegistration] = []
        for reg in self._agents.values():
            if reg.name in completed or reg.name in pending:
                continue
            deps = self.get_dependencies(reg.name)
            if all(d in completed for d in deps):
                executable.append(reg)
        return executable

    def getParallelGroups(
        self, completed: list[str]
    ) -> list[list[str]]:
        """Compute groups of agents that can execute in parallel.

        Returns a list of groups; each group contains agents whose
        dependencies are satisfied once all previous groups complete.
        """
        groups: list[list[str]] = []
        remaining = set(self._agents.keys()) - set(completed)

        while remaining:
            ready = []
            for name in sorted(remaining):
                deps = set(self.get_dependencies(name))
                if deps <= set(completed):
                    ready.append(name)
            if not ready:
                break
            groups.append(ready)
            completed = list(set(completed) | set(ready))
            remaining -= set(ready)

        return groups

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "total_agents": len(self._agents),
            "agents": {
                name: {
                    "role": reg.role,
                    "capabilities": [c.name for c in reg.capabilities],
                    "can_run_in_parallel": reg.can_run_in_parallel,
                    "requires_human_approval": reg.requires_human_approval,
                    "max_retries": reg.max_retries,
                    "timeout_seconds": reg.timeout_seconds,
                }
                for name, reg in self._agents.items()
            },
        }


class AgentCapabilityRegistry:
    """Tracks the capability graph -- which agents produce and consume
    which data types.  Used by the supervisor for dependency-aware scheduling.

    This is a lightweight index over the capabilities declared in
    ``AgentRegistration`` records.
    """

    def __init__(self, agent_registry: AgentRegistry) -> None:
        self._agent_registry = agent_registry
        self._producers: dict[str, list[str]] = {}
        self._consumers: dict[str, list[str]] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        self._producers.clear()
        self._consumers.clear()
        for reg in self._agent_registry.list_agents():
            for cap in reg.capabilities:
                for out in cap.output_types:
                    self._producers.setdefault(out, []).append(reg.name)
                for inp in cap.input_types:
                    self._consumers.setdefault(inp, []).append(reg.name)

    def refresh(self) -> None:
        self._rebuild()

    def producers_of(self, capability: str) -> list[str]:
        return list(self._producers.get(capability, []))

    def consumers_of(self, capability: str) -> list[str]:
        return list(self._consumers.get(capability, []))

    def unsatisfied_capabilities(self, completed_agents: list[str]) -> list[str]:
        """Return capabilities that no completed agent has produced yet."""
        produced: set[str] = set()
        for name in completed_agents:
            reg = self._agent_registry.get(name)
            if reg is None:
                continue
            for cap in reg.capabilities:
                produced.update(cap.output_types)
        all_consumed: set[str] = set()
        for consumers in self._consumers.values():
            all_consumed.update(consumers)
        unsatisfied: list[str] = []
        for cap_name in self._consumers:
            if cap_name not in produced:
                unsatisfied.append(cap_name)
        return unsatisfied

    def dependency_chain(self, agent_name: str) -> list[list[str]]:
        """Return the full dependency chain for an agent, level by level."""
        chain: list[list[str]] = []
        visited: set[str] = set()
        current_level = [agent_name]

        while current_level:
            chain.append(list(current_level))
            visited.update(current_level)
            next_level: list[str] = []
            for name in current_level:
                deps = self._agent_registry.get_dependencies(name)
                for d in deps:
                    if d not in visited:
                        next_level.append(d)
            current_level = list(set(next_level))

        return chain[1:] if chain else []

    def summary(self) -> dict[str, Any]:
        return {
            "producers": dict(self._producers),
            "consumers": dict(self._consumers),
        }
