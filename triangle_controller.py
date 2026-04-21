from pox.core import core
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
import pox.lib.packet as pkt

log = core.getLogger()

H1_MAC = "00:00:00:00:00:01"
H2_MAC = "00:00:00:00:00:02"

S1, S2, S3 = 1, 2, 3

# Verified port layout:
# s1: port1=h1,  port2=s2(primary), port3=s3(backup)
# s2: port1=h2,  port2=s1(primary), port3=s3(backup)
# s3: port1=s1,  port2=s2

class TriangleController(EventMixin):

    def __init__(self):
        self.connections = {}
        self.primary_down = False
        self.listenTo(core.openflow)
        log.info("TriangleController started")

    def _handle_ConnectionUp(self, event):
        dpid = event.dpid
        self.connections[dpid] = event.connection
        log.info("Switch connected: dpid=%s (total=%s)", dpid, len(self.connections))
        self._install_table_miss(event.connection)
        if len(self.connections) == 3:
            log.info("All 3 switches up — installing primary rules")
            self._flush_all()
            self._install_primary_rules()

    def _handle_ConnectionDown(self, event):
        self.connections.pop(event.dpid, None)
        log.warning("Switch disconnected: dpid=%s", event.dpid)

    def _install_table_miss(self, conn):
        msg = of.ofp_flow_mod()
        msg.priority = 0
        msg.actions.append(of.ofp_action_output(port=of.OFPP_CONTROLLER))
        conn.send(msg)

    # ------------------------------------------------------------------ #
    # PacketIn: forward ALL packets (ARP + ICMP) manually via port table  #
    # ------------------------------------------------------------------ #
    def _handle_PacketIn(self, event):
        packet  = event.parsed
        if not packet.parsed:
            return

        dpid    = event.dpid
        in_port = event.port
        src_mac = str(packet.src)
        dst_mac = str(packet.dst)

        log.info("[PKT_IN] dpid=%s in_port=%s src=%s dst=%s type=%s",
                 dpid, in_port, src_mac, dst_mac,
                 "ARP" if packet.type == pkt.ethernet.ARP_TYPE else
                 "ICMP" if packet.type == pkt.ethernet.IP_TYPE else hex(packet.type))

        # Get correct output port for this packet
        out_port = self._get_out_port(dpid, in_port, src_mac, dst_mac)

        if out_port is not None:
            log.info("[FORWARD] dpid=%s in_port=%s -> out_port=%s", dpid, in_port, out_port)
            self._send_packet_out(event, out_port)
        else:
            log.warning("[DROP] dpid=%s in_port=%s src=%s dst=%s — no route",
                        dpid, in_port, src_mac, dst_mac)

    def _get_out_port(self, dpid, in_port, src_mac, dst_mac):
        if not self.primary_down:
            # PRIMARY: h1 - s1(p1->p2) - s2(p1->p2) - h2
            table = {
                S1: {1: 2,  2: 1},   # h1->s2, s2->h1
                S2: {1: 2,  2: 1},   # s1->h2, h2->s1
            }
        else:
            # BACKUP: h1 - s1(p1->p3) - s3(p1->p2) - s2(p3->p2) - h2
            table = {
                S1: {1: 3,  3: 1},   # h1->s3, s3->h1
                S3: {1: 2,  2: 1},   # s1->s2, s2->s1
                S2: {3: 2,  2: 3},   # s3->h2, h2->s3
            }
        return table.get(dpid, {}).get(in_port, None)

    def _send_packet_out(self, event, out_port):
        msg         = of.ofp_packet_out()
        msg.in_port = event.port
        # Use raw packet data (works even when n_buffers=0)
        if event.ofp.buffer_id != of.NO_BUFFER:
            msg.buffer_id = event.ofp.buffer_id
        else:
            msg.data = event.ofp.data
        msg.actions.append(of.ofp_action_output(port=out_port))
        event.connection.send(msg)

    # ------------------------------------------------------------------ #
    # Flow rules                                                          #
    # ------------------------------------------------------------------ #
    def _install_primary_rules(self):
        s1 = self.connections.get(S1)
        s2 = self.connections.get(S2)
        if not all([s1, s2]):
            return

        # S1: port1=h1, port2=s2
        self._add_flow(s1, H1_MAC, H2_MAC, out_port=2, priority=20)
        self._add_flow(s1, H2_MAC, H1_MAC, out_port=1, priority=20)
        # S2: port1=s1, port2=h2
        self._add_flow(s2, H1_MAC, H2_MAC, out_port=2, priority=20)
        self._add_flow(s2, H2_MAC, H1_MAC, out_port=1, priority=20)

        self.primary_down = False
        log.info("[PRIMARY PATH ACTIVE] h1 <-> h2 via s1-s2")

    def _install_backup_rules(self):
        s1 = self.connections.get(S1)
        s2 = self.connections.get(S2)
        s3 = self.connections.get(S3)
        if not all([s1, s2, s3]):
            return

        # S1: port1=h1, port3=s3
        self._add_flow(s1, H1_MAC, H2_MAC, out_port=3, priority=30)
        self._add_flow(s1, H2_MAC, H1_MAC, out_port=1, priority=30)
        # S3: port1=s1, port2=s2
        self._add_flow(s3, H1_MAC, H2_MAC, out_port=2, priority=30)
        self._add_flow(s3, H2_MAC, H1_MAC, out_port=1, priority=30)
        # S2: port3=s3, port2=h2
        self._add_flow(s2, H1_MAC, H2_MAC, out_port=2, priority=30)
        self._add_flow(s2, H2_MAC, H1_MAC, out_port=3, priority=30)

        self.primary_down = True
        log.info("[BACKUP PATH ACTIVE] h1 <-> h2 via s1-s3-s2")

    def _add_flow(self, conn, src_mac, dst_mac, out_port, priority=20):
        msg              = of.ofp_flow_mod()
        msg.match.dl_src = of.EthAddr(src_mac)
        msg.match.dl_dst = of.EthAddr(dst_mac)
        msg.priority     = priority
        msg.idle_timeout = 0
        msg.hard_timeout = 0
        msg.actions.append(of.ofp_action_output(port=out_port))
        conn.send(msg)
        log.debug("[FLOW] dpid=%s %s->%s out=%s", conn.dpid, src_mac, dst_mac, out_port)

    def _flush_all(self):
        log.info("[FLUSH] Clearing all flows")
        for dpid, conn in self.connections.items():
            conn.send(of.ofp_flow_mod(command=of.OFPFC_DELETE))
            self._install_table_miss(conn)

    # ------------------------------------------------------------------ #
    # Port failure detection                                              #
    # ------------------------------------------------------------------ #
    def _handle_PortStatus(self, event):
        dpid   = event.dpid
        port   = event.ofp.desc.port_no
        reason = event.ofp.reason

        OFPPR_DELETE    = 1
        OFPPR_MODIFY    = 2
        OFPPS_LINK_DOWN = 1

        if port > 50:
            return

        link_down = False
        if reason == OFPPR_DELETE:
            link_down = True
        elif reason == OFPPR_MODIFY:
            if event.ofp.desc.state & OFPPS_LINK_DOWN:
                link_down = True
            else:
                if self.primary_down:
                    log.info("[RECOVERY] Port %s dpid=%s UP — restoring primary", port, dpid)
                    self._flush_all()
                    self._install_primary_rules()
                return

        if link_down:
            if (dpid == S1 and port == 2) or (dpid == S2 and port == 2):
                log.warning("[FAILURE] Primary link DOWN dpid=%s port=%s — rerouting via s3", dpid, port)
                self._flush_all()
                self._install_backup_rules()


def launch():
    core.registerNew(TriangleController)
    log.info("Triangle Controller launched")
