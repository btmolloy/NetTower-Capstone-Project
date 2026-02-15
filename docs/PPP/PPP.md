# Project Plan Presentation (PPP)


Project: NetTower
Author: Benjamin Molloy

ASE 485 Capstone


## Problem/Domain

Small or disrupted networks lack a simple way to quickly
understand what devices are present and how they are generally
connected.

- Small networks (home labs, ad-hoc, off-grid, disaster-affected)
- No centralized monitoring or enterprise tooling
- Limited visibility into what devices are present and reachable
- Existing tools require deep networking expertise and complex
    interpretation


## Project Overview

- **What?** A network situational awareness tool that provides a high-level
    overview of small or disrupted networks.
- **Who?** Home lab users, responders, and administrators working in small, off-
    grid, or degraded network environments.
- **Why?** When infrastructure is limited or disrupted, existing tools are too
    complex or slow to provide a clear understanding of what devices and
    connectivity still exist.
- **How?** By discovering reachable devices, inferring high-level connectivity, and
    visualizing the network in an easy-to-understand format with minimal
    configuration.


## Goals & Objectives

**Primary Goal:**
Provide fast, understandable network situational awareness for
small or disrupted networks.

**Objectives:**

- Discover reachable devices
- Infer high-level connectivity relationships
- Present an intuitive network visualization
- Support rapid understanding by moderately technical users


## Core Features

- **Network Topology View** (2D and optional 3D)
- **Node-Centric Exploration** with expandable device details
- **Host Identification & Classification** with visual differentiation
- **Connectivity Representation** showing observed or inferred
    relationships
- **Activity / Density Heat Mapping**
- **Dynamic Network State Updates**
- **Interactive Network Navigation**
- **User-Controlled Scanning & Discovery Settings**


## Sprints 1 & 2

```
Sprint 1

Phase      Date      Focus
S1W1 2/9/26 – 2/23/26 Project setup and baseline agentless discovery
S1W2 2/24/26 – 3/9/26 Network scanning and host identification
S1W3 3/10/26 – 3/24/26 Basic connectivity inference and relationship modeling
S1W4 3/25/26 – 4/7/26 Initial topology visualization

*Subject to adjustments
```
```
Sprint 2

Phase      Date      Focus
S2W1 4/8/26 – 4/14/26 Visualization enhancements
S2W2 4/15/26 – 4/21/26 Refinement and performance testing
S2W3 4/22/26 – 4/28/26 Documentation and publication prep
S2W4 4/29/26 – 5/1/26 Final testing, demo, and submission

*Subject to adjustments
```

## Tools and Technologies

- **Languages:** Python, JavaScript, HTML, CSS (subject to refinement)
- **Supporting Technologies:** REST-style APIs/JSON data exchange, MongoDB
- **Visualization:** Web-based UI
- **Networking:** tcpdump, ICMP utilities, traceroute, ARP utilities, nmap
- **Platform:** Local or self-hosted execution


## Challenges

- Incomplete or misleading network data
- Inferring relationships without full visibility
- Representing uncertainty clearly in visualization
- Balancing simplicity with functionality
- Reaching all segmented areas of the network
- Meeting deadlines with military obligations


## Publication of Results

- NetTower will be published as a web-based project page that documents the system’s purpose, design, and capabilities, along with methods for purchase.
- It will also be posted on my Portfolio.


## Learning with AI

- **Topics to Learn with AI:**
    - Layer 2, 3 and 4 protocol behavior, limitations and capabilities
    - Break down of traffic packets down to its binary

- **How AI Is Used:**
    - Breaking down protocol mechanics
    - Exploring inference limits and edge cases
    - Supporting design decisions for discovery and visualization


## Questions?


