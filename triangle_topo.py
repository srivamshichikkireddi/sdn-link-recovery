#!/usr/bin/env python3
# Triangle topology:
#       h1          h2
#       |            |
#      s1 --------- s2
#        \         /
#            s3
#
# Primary path:  h1 - s1 - s2 - h2
# Backup path:   h1 - s1 - s3 - s2 - h2

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI

class TriangleTopo(Topo):
    def build(self):
        # Hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')

        # Switches
        s1 = self.addSwitch('s1', dpid='0000000000000001')
        s2 = self.addSwitch('s2', dpid='0000000000000002')
        s3 = self.addSwitch('s3', dpid='0000000000000003')

        # Links — ORDER MATTERS for port numbering
        # s1: port1=h1, port2=s2, port3=s3
        self.addLink(h1, s1)   # s1-port1
        self.addLink(s1, s2)   # s1-port2, s2-port2 (primary)
        self.addLink(s1, s3)   # s1-port3, s3-port1 (backup)

        # s2: port1=h2, port2=s1, port3=s3
        self.addLink(h2, s2)   # s2-port1
        self.addLink(s2, s3)   # s2-port3, s3-port2 (backup)

def run():
    setLogLevel('info')
    topo = TriangleTopo()
    net = Mininet(
        topo=topo,
        controller=RemoteController('c0', ip='127.0.0.1', port=6633),
        switch=OVSSwitch,
        autoSetMacs=False   # we set MACs manually above
    )
    net.start()

    info('\n===========================================\n')
    info('  Triangle Topology Ready\n')
    info('  Primary path:  h1 - s1 - s2 - h2\n')
    info('  Backup path:   h1 - s1 - s3 - s2 - h2\n')
    info('===========================================\n')
    info('\nTEST COMMANDS:\n')
    info('  Normal:  pingall\n')
    info('  Failure: link s1 s2 down  then  h1 ping -c 4 h2\n')
    info('  Recover: link s1 s2 up    then  pingall\n')
    info('===========================================\n\n')

    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()
