# SDN Link Failure Detection and Recovery
### Mininet + POX Controller | OpenFlow | Triangle Topology

---

## Problem Statement

In traditional networks, when a link fails, traffic is disrupted until manual intervention restores it. This project implements an **SDN-based solution** that automatically detects link failures and reroutes traffic through an alternate path — with zero manual intervention — using Mininet and a custom POX OpenFlow controller.

---

## Topology

```
    h1              h2
    |                |
   s1 —————————— s2
     \            /
          s3

Primary path : h1 → s1 → s2 → h2
Backup path  : h1 → s1 → s3 → s2 → h2
```

| Device | Role |
|--------|------|
| h1, h2 | Hosts (10.0.0.1, 10.0.0.2) |
| s1, s2, s3 | OpenFlow switches (OVS) |
| POX | SDN Controller |

---

## Features

- Proactive flow rule installation (no flooding for known traffic)
- Automatic link failure detection via OpenFlow `PortStatus` events
- Dynamic rerouting through backup path (via s3) on primary link failure
- Automatic restoration of primary path when link recovers
- ARP and ICMP packet handling via `PacketIn` fallback

---

## Project Structure

```
sdn_triangle/
├── triangle_controller.py   # POX controller logic
├── triangle_topo.py         # Mininet triangle topology
└── README.md                # This file
```

---

## Setup and Installation

### Prerequisites
- Ubuntu 20.04 / 22.04
- Python 3.x
- Mininet
- POX controller
- Open vSwitch

### Install Mininet
```bash
sudo apt update
sudo apt install mininet -y
```

### Install POX
```bash
cd ~
git clone https://github.com/noxrepo/pox.git
```

### Clone this repository
```bash
git clone https://github.com/<your-username>/sdn-link-recovery.git
cd sdn-link-recovery
```

### Copy controller to POX
```bash
cp triangle_controller.py ~/pox/pox/triangle_controller.py
```

---

## Running the Project

### Step 1 — Start the POX controller (Terminal 1)
```bash
cd ~/pox
python3 pox.py log.level --DEBUG triangle_controller
```

Expected output:
```
INFO:triangle_controller:TriangleController started
INFO:core:POX 0.7.0 (gar) is up.
INFO:openflow.of_01:Listening on 0.0.0.0:6633
```

### Step 2 — Start the Mininet topology (Terminal 2)
```bash
sudo mn -c && sudo python3 triangle_topo.py
```

Expected output:
```
*** Triangle Topology Ready
*** Primary path:  h1 - s1 - s2 - h2
*** Backup path:   h1 - s1 - s3 - s2 - h2
mininet>
```

### Step 3 — Set static ARP (inside Mininet CLI)
```bash
mininet> h1 arp -s 10.0.0.2 00:00:00:00:00:02
mininet> h2 arp -s 10.0.0.1 00:00:00:00:00:01
```

---

## Test Scenarios

### Scenario 1 — Normal Forwarding (Primary Path)
```bash
mininet> h1 ping -c 4 h2
```
**Expected:** 0% packet loss. Traffic flows via `s1 → s2`.

---

### Scenario 2 — Link Failure and Rerouting (Backup Path)
```bash
mininet> link s1 s2 down
mininet> h1 ping -c 4 h2
```
**Expected:** Traffic automatically reroutes via `s1 → s3 → s2`. 0% packet loss.

POX terminal will show:
```
WARNING: [FAILURE] Primary link DOWN — rerouting via s3
INFO:    [BACKUP PATH ACTIVE] h1 <-> h2 via s1-s3-s2
```

---

### Scenario 3 — Link Recovery (Primary Path Restored)
```bash
mininet> link s1 s2 up
mininet> h1 ping -c 4 h2
```
**Expected:** Traffic returns to primary path `s1 → s2`. 0% packet loss.

---

## Performance Measurements

### Latency (ping)
```bash
mininet> h1 ping -c 10 h2
```

### Throughput (iperf)
```bash
mininet> iperf h1 h2
```

### Flow Table Inspection
```bash
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-ofctl dump-flows s2
mininet> sh ovs-ofctl dump-flows s3
```

---

## Expected Output Screenshots

> Add your screenshots here showing:
> - `pingall` with 0% loss (normal)
> - `ping` with rerouting after `link s1 s2 down`
> - Flow tables before and after failure (`ovs-ofctl dump-flows`)
> - POX terminal logs showing `[FAILURE]` and `[BACKUP PATH ACTIVE]`

---

## Cleanup

```bash
mininet> exit
sudo mn -c
```

---

## SDN Concepts Demonstrated

| Concept | Implementation |
|---------|----------------|
| Controller-Switch interaction | POX connects to OVS via OpenFlow on port 6633 |
| Flow rule design (match-action) | MAC src+dst matched, output port as action |
| Packet-in handling | ARP and unmatched packets forwarded by controller |
| Topology change detection | `PortStatus` events trigger rerouting |
| Proactive flow installation | Rules pushed to switches on startup |

---

## References

- [Mininet Overview](https://mininet.org/overview/)
- [Mininet Walkthrough](https://mininet.org/walkthrough/)
- [POX Wiki](https://noxrepo.github.io/pox-doc/html/)
- [OpenFlow 1.0 Specification](https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf)
- [Open vSwitch Documentation](https://docs.openvswitch.org/)# sdn-link-recovery
