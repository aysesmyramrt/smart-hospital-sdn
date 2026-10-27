"""
Smart Hospital Network — RYU SDN Controller
NGN 2025 | KFAU-KGTU

OpenFlow 1.3 controller:
  - Slice A (URLLC): 10.0.x.x  →  Queue 0, Priority 300
  - Slice B (mIoT) : 10.1.x.x  →  Queue 1, Priority 200
  - Slice C (eMBB) : 10.2.x.x  →  Queue 2, Priority 100
"""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4


class SmartHospitalController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # IP prefix → (queue_id, priority, slice_name)
    SLICES = {
        '10.0.': (0, 300, 'URLLC'),
        '10.1.': (1, 200, 'mIoT'),
        '10.2.': (2, 100, 'eMBB'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port: dict = {}
        self.logger.info("=" * 56)
        self.logger.info("  Smart Hospital SDN Controller — OpenFlow 1.3")
        self.logger.info("  NGN 2025 | KFAU-KGTU")
        self.logger.info("=" * 56)

    # ── Switch connects ───────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp     = ev.msg.datapath
        ofp    = dp.ofproto
        parser = dp.ofproto_parser

        # Table-miss: send to controller
        match   = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        self._add_flow(dp, 0, match, actions)

        self.logger.info(f"[CTRL] Switch {dp.id} connected — installing slice rules")
        self._install_default_rules(dp)

    def _install_default_rules(self, dp):
        """Pre-install IP-prefix → queue flow rules."""
        ofp    = dp.ofproto
        parser = dp.ofproto_parser

        for prefix, (queue_id, priority, name) in self.SLICES.items():
            # Build wildcard IP match (first two octets)
            parts = prefix.rstrip('.').split('.')
            ip_base = '.'.join(parts) + '.0.0'
            mask    = '255.255.0.0' if len(parts) == 2 else '255.0.0.0'

            match = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=(ip_base, mask),
            )
            actions = [
                parser.OFPActionSetQueue(queue_id),
                parser.OFPActionOutput(ofp.OFPP_NORMAL),
            ]
            self._add_flow(dp, priority, match, actions)
            self.logger.info(
                f"[FLOW] {name:5s} | src={ip_base}/{mask} "
                f"| queue={queue_id} | priority={priority}"
            )

    # ── Packet-in (learning switch fallback) ─────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg     = ev.msg
        dp      = msg.datapath
        ofp     = dp.ofproto
        parser  = dp.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst, src, dpid = eth.dst, eth.src, dp.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        out_port = self.mac_to_port[dpid].get(dst, ofp.OFPP_FLOOD)

        # Classify packet
        queue_id, priority = 2, 100  # default: eMBB
        ip_pkts = pkt.get_protocols(ipv4.ipv4)
        if ip_pkts:
            src_ip = ip_pkts[0].src
            for prefix, (q, p, _) in self.SLICES.items():
                if src_ip.startswith(prefix):
                    queue_id, priority = q, p
                    break

        actions = [parser.OFPActionSetQueue(queue_id),
                   parser.OFPActionOutput(out_port)]

        # Install exact-match flow to skip future packet_in
        if out_port != ofp.OFPP_FLOOD and ip_pkts:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ip_pkts[0].src,
                ipv4_dst=ip_pkts[0].dst,
            )
            if msg.buffer_id != ofp.OFP_NO_BUFFER:
                self._add_flow(dp, priority, match, actions, msg.buffer_id)
                return
            self._add_flow(dp, priority, match, actions)

        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        out  = parser.OFPPacketOut(
            datapath=dp, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data,
        )
        dp.send_msg(out)

    # ── Helper ────────────────────────────────────────────────────
    def _add_flow(self, dp, priority, match, actions, buffer_id=None):
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        inst   = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        kwargs = dict(datapath=dp, priority=priority, match=match, instructions=inst)
        if buffer_id and buffer_id != ofp.OFP_NO_BUFFER:
            kwargs['buffer_id'] = buffer_id
        dp.send_msg(parser.OFPFlowMod(**kwargs))
