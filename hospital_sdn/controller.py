from __future__ import annotations
from .models import SliceType, FlowRule, SLICE_CFG


class SDNController:
    """
    Simulated RYU SDN Controller — OpenFlow 1.3
    Manages flow tables, classifies traffic, and enforces QoS policy.
    """

    def __init__(self):
        self.flow_table: list[FlowRule] = []
        self.events: list[str] = []
        self._install_default_flows()

    # ── Flow rule management ──────────────────────────────────────────────────

    def _install_default_flows(self) -> None:
        """Push OpenFlow rules to virtual switches at startup."""
        rules = [
            # Slice A — URLLC — strict priority queue 0
            FlowRule("urllc_icu",   SliceType.URLLC, "10.0.1.", 300, 0),
            FlowRule("urllc_or",    SliceType.URLLC, "10.0.2.", 300, 0),
            FlowRule("urllc_emerg", SliceType.URLLC, "10.0.3.", 300, 0),
            # Slice B — mIoT — priority queue 1
            FlowRule("miot_wear",   SliceType.mIoT,  "10.1.1.", 200, 1),
            FlowRule("miot_sens",   SliceType.mIoT,  "10.1.2.", 200, 1),
            # Slice C — eMBB — best-effort queue 2
            FlowRule("embb_staff",  SliceType.eMBB,  "10.2.1.", 100, 2),
            FlowRule("embb_admin",  SliceType.eMBB,  "10.2.2.", 100, 2),
        ]
        self.flow_table = rules
        self.log(f"[CTRL] Flow tables installed — {len(rules)} rules across 3 slices")

    def classify(self, src_ip: str) -> SliceType:
        """Match ingress packet to its slice via OpenFlow longest-prefix match."""
        for rule in sorted(self.flow_table, key=lambda r: -r.priority):
            if src_ip.startswith(rule.match_prefix):
                return rule.slice_type
        return SliceType.eMBB  # default: best-effort

    # ── Event logging ─────────────────────────────────────────────────────────

    def log(self, msg: str) -> None:
        self.events.append(msg)
        if len(self.events) > 40:
            self.events.pop(0)
