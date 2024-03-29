#!/usr/bin/python

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI


class part1_topo(Topo):
    def build(self):
        s1 = self.addSwitch('s1')
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')

        self.addLink(s1, h1)
        self.addLink(s1, h2)
        self.addLink(s1, h3)
        self.addLink(s1, h4)


topos = {'part1': part1_topo}

if __name__ == '__main__':
    t = part1_topo()
    net = Mininet(topo=t)
    net.run()
    CLI(net)
    net.stop()
