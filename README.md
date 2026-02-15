<h1 data-start="234" data-end="247"><span style="font-size: 36pt;">NetTower - Capstone</span></h1>
<h1 data-start="340" data-end="359"><strong data-start="342" data-end="359">Project Links</strong></h1>
<ul data-start="361" data-end="500">
    <li data-start="361" data-end="405">
        <p data-start="363" data-end="405">GitHub Repository: <a href="https://github.com/btmolloy/NetTower-Capstone-Project" target="_blank" rel="noopener">https://github.com/btmolloy/NetTower-Capstone-Project</a>&nbsp;</p>
    </li>
    <li data-start="361" data-end="405">PPP Document: <a href="https://github.com/btmolloy/NetTower-Capstone-Project/blob/main/docs/PPP/PPP%20-%20NetTower.pdf" target="_blank" rel="noopener">https://github.com/btmolloy/NetTower-Capstone-Project/blob/main/docs/PPP/PPP%20-%20NetTower.pdf</a>&nbsp;</li>
    <li data-start="406" data-end="454">
        <p data-start="408" data-end="454">Project Documentation: <a href="https://github.com/btmolloy/NetTower-Capstone-Project/tree/main/docs" target="_blank" rel="noopener">https://github.com/btmolloy/NetTower-Capstone-Project/tree/main/docs</a>&nbsp;</p>
    </li>
    <li data-start="406" data-end="454">Learning with AI Repository: &nbsp;<a href="https://github.com/btmolloy/Learning-With-AI" target="_blank" rel="noopener">https://github.com/btmolloy/Learning-With-AI</a>&nbsp;</li>
</ul>
<hr data-start="502" data-end="505" />
<h1 data-start="507" data-end="529"><strong data-start="509" data-end="529">Project Overview</strong></h1>
<p data-start="531" data-end="904">NetTower is a network situational awareness tool designed to provide a clear, high-level overview of small, ad-hoc, or disrupted networks. The system focuses on helping moderately technical users quickly understand what devices are present, reachable, and how they are generally connected&mdash;without requiring enterprise monitoring infrastructure or deep networking expertise.</p>
<p data-start="531" data-end="904">&nbsp;</p>
<hr data-start="906" data-end="909" />
<h1 data-start="911" data-end="931"><strong data-start="913" data-end="931">Problem Domain</strong></h1>
<p data-start="933" data-end="1063">Small or disrupted networks lack a simple way to quickly understand what devices are present and how they are generally connected.</p>
<p data-start="1065" data-end="1373">In environments such as home labs, off-grid networks, or infrastructure-limited situations, centralized monitoring tools are often unavailable or impractical. Existing solutions tend to be complex, traffic-heavy, and designed for enterprise environments, making them difficult to interpret or deploy quickly.</p>
<p data-start="1065" data-end="1373">&nbsp;</p>
<hr data-start="1375" data-end="1378" />
<h1 data-start="1380" data-end="1403"><strong data-start="1382" data-end="1403">Solution Overview</strong></h1>
<p data-start="1405" data-end="1721">NetTower provides a lightweight, quickly deployable system that discovers reachable devices, infers high-level connectivity relationships, and presents the results through an intuitive network visualization. The focus is on clarity and accessibility rather than deep packet inspection or enterprise-scale monitoring.</p>
<p data-start="1405" data-end="1721">&nbsp;</p>
<hr data-start="1723" data-end="1726" />
<h1 data-start="1728" data-end="1742"><strong data-start="1730" data-end="1742">Features</strong></h1>
<ul data-start="1744" data-end="2133">
    <li data-start="1744" data-end="1788">
        <p data-start="84" data-end="133"><strong data-start="84" data-end="133">1) Network Topology View (2D and optional 3D)</strong></p>
        <ul data-start="134" data-end="312">
            <li data-start="134" data-end="208">
                <p data-start="136" data-end="208">The system shall represent discovered devices as a visual topology view.</p>
            </li>
            <li data-start="209" data-end="255">
                <p data-start="211" data-end="255">The system shall support a 2D topology view.</p>
            </li>
            <li data-start="256" data-end="312">
                <p data-start="258" data-end="312">The system shall support an optional 3D topology view.</p>
            </li>
        </ul>
        <p data-start="314" data-end="345"><strong data-start="314" data-end="345">2) Node-Centric Exploration</strong></p>
        <ul data-start="346" data-end="504">
            <li data-start="346" data-end="419">
                <p data-start="348" data-end="419">The system shall represent each discovered device as a selectable node.</p>
            </li>
            <li data-start="420" data-end="504">
                <p data-start="422" data-end="504">The system shall allow users to expand a node to view detailed device information.</p>
            </li>
        </ul>
        <p data-start="506" data-end="549"><strong data-start="506" data-end="549">3) Host Identification &amp; Classification</strong></p>
        <ul data-start="550" data-end="728">
            <li data-start="550" data-end="650">
                <p data-start="552" data-end="650">The system shall identify devices based on observed characteristics (e.g., OS family/device type).</p>
            </li>
            <li data-start="651" data-end="728">
                <p data-start="653" data-end="728">The system shall visually differentiate nodes based on host classification.</p>
            </li>
        </ul>
        <p data-start="730" data-end="764"><strong data-start="730" data-end="764">4) Connectivity Representation</strong></p>
        <ul data-start="765" data-end="941">
            <li data-start="765" data-end="856">
                <p data-start="767" data-end="856">The system shall display observed or inferred connectivity relationships between devices.</p>
            </li>
            <li data-start="857" data-end="941">
                <p data-start="859" data-end="941">The system shall render relationships as links between nodes in the topology view.</p>
            </li>
        </ul>
        <p data-start="943" data-end="981"><strong data-start="943" data-end="981">5) Activity / Density Heat Mapping</strong></p>
        <ul data-start="982" data-end="1165">
            <li data-start="982" data-end="1088">
                <p data-start="984" data-end="1088">The system shall provide an optional heat-map overlay showing relative activity or device concentration.</p>
            </li>
            <li data-start="1089" data-end="1165">
                <p data-start="1091" data-end="1165">The system shall update the overlay to reflect current network state data.</p>
            </li>
        </ul>
        <p data-start="1167" data-end="1203"><strong data-start="1167" data-end="1203">6) Dynamic Network State Updates</strong></p>
        <ul data-start="1204" data-end="1386">
            <li data-start="1204" data-end="1297">
                <p data-start="1206" data-end="1297">The system shall update the visualization when devices appear, disappear, or change status.</p>
            </li>
            <li data-start="1298" data-end="1386">
                <p data-start="1300" data-end="1386">The system shall maintain the current network view to reflect the latest scan results.</p>
            </li>
        </ul>
        <p data-start="1388" data-end="1425"><strong data-start="1388" data-end="1425">7) Interactive Network Navigation</strong></p>
        <ul data-start="1426" data-end="1572">
            <li data-start="1426" data-end="1490">
                <p data-start="1428" data-end="1490">The system shall allow users to pan and zoom the network view.</p>
            </li>
            <li data-start="1491" data-end="1572">
                <p data-start="1493" data-end="1572">The system shall allow users to reposition nodes to support focused inspection.</p>
            </li>
        </ul>
        <p data-start="1574" data-end="1626"><strong data-start="1574" data-end="1626">8) User-Controlled Scanning &amp; Discovery Settings</strong></p>
        <ul data-start="1627" data-end="1826" data-is-last-node="" data-is-only-node="">
            <li data-start="1627" data-end="1726">
                <p data-start="1629" data-end="1726">The system shall allow users to discover reachable devices on a local or specified network range.</p>
            </li>
            <li data-start="1727" data-end="1826" data-is-last-node="">
                <p data-start="1729" data-end="1826" data-is-last-node="">The system shall support adjustable scan settings (e.g., scan frequency and target range/subnet).</p>
            </li>
        </ul>
    </li>
</ul>
<p>&nbsp;</p>
<hr data-start="2676" data-end="2679" />
<h1 data-start="2681" data-end="2725"><strong data-start="2683" data-end="2725">System Architecture / Technical Design</strong></h1>
<p data-start="2727" data-end="2752">NetTower will consist of:</p>
<ul data-start="2754" data-end="3067">
    <li data-start="2754" data-end="2842">
        <p data-start="2756" data-end="2842">A <strong data-start="2758" data-end="2781">discovery component</strong> responsible for scanning and collecting network information.</p>
    </li>
    <li data-start="2843" data-end="2919">
        <p data-start="2845" data-end="2919">A <strong data-start="2847" data-end="2870">data modeling layer</strong> that stores device and connectivity information.</p>
    </li>
    <li data-start="2920" data-end="2992">
        <p data-start="2922" data-end="2992">A <strong data-start="2924" data-end="2957">web-based visualization layer</strong> that renders the network topology.</p>
    </li>
    <li data-start="2993" data-end="3067">
        <p data-start="2995" data-end="3067">A <strong data-start="2997" data-end="3018">control interface</strong> that allows users to adjust scanning parameters.</p>
    </li>
</ul>
<p data-start="3069" data-end="3201">The system will operate locally or in a self-hosted environment and will not rely on external cloud services for core functionality.</p>
<p data-start="3069" data-end="3201">&nbsp;</p>
<h3 data-start="3069" data-end="3201">Project Architecture (In Progress)</h3>
<p data-start="3069" data-end="3201">NetTower/<br />│<br />├── backEnd/<br />│&nbsp; &nbsp;<br />│&nbsp; &nbsp;<br />│<br />├── frontEnd/<br />│&nbsp;&nbsp;<br />│&nbsp; &nbsp;<br />│&nbsp; &nbsp;<br />│<br />└── tests/<br />&nbsp;&nbsp;</p>
<hr data-start="3203" data-end="3206" />
<h1 data-start="3208" data-end="3238"><strong data-start="3210" data-end="3238">Sprint Plan / Hard Deadlines</strong></h1>
<ul data-start="3463" data-end="3660">
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprints 1 &amp; 2 (Subject to adjustments)</p>
    </li>
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprint 1<br />Phase Date Focus<br />S1W1 2/9/26 &ndash; 2/23/26 Project setup and baseline agentless discovery<br />S1W2 2/24/26 &ndash; 3/9/26 Network scanning and host identification<br />S1W3 3/10/26 &ndash; 3/24/26 Basic connectivity inference and relationship modeling<br />S1W4 3/25/26 &ndash; 4/7/26 Initial topology visualization</p>
    </li>
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprint 2<br />Phase Date Focus<br />S2W1 4/8/26 &ndash; 4/14/26 Visualization enhancements<br />S2W2 4/15/26 &ndash; 4/21/26 Refinement and performance testing<br />S2W3 4/22/26 &ndash; 4/28/26 Documentation and publication prep<br />S2W4 4/29/26 &ndash; 5/1/26 Final testing, demo, and submission</p>
    </li>
</ul>
<h3>Deadlines:</h3>
<ul data-start="3463" data-end="3660">
    <li data-start="3636" data-end="3660">
        <p data-start="36" data-end="99"><strong data-start="36" data-end="71">Hard Deadline 1 &ndash; March 9, 2026</strong><br data-start="71" data-end="74" />Core Discovery Complete</p>
        <p data-start="101" data-end="167">&nbsp;</p>
    </li>
    <li data-start="3636" data-end="3660">
        <p data-start="101" data-end="167"><strong data-start="101" data-end="136">Hard Deadline 2 &ndash; April 7, 2026</strong><br data-start="136" data-end="139" />Functional Prototype Ready</p>
        <p data-start="169" data-end="227" data-is-last-node="" data-is-only-node="">&nbsp;</p>
    </li>
    <li data-start="3636" data-end="3660"><strong>Hard Deadline 3 &ndash; April 21, 2026</strong><br />Refinement &amp; Testing Complete</li>
    <li data-start="3636" data-end="3660">
        <p data-start="169" data-end="227" data-is-last-node="" data-is-only-node=""><strong data-start="169" data-end="202">Hard Deadline 3 &ndash; May 1, 2026</strong><br data-start="202" data-end="205" />Finalized &amp; Published</p>
    </li>
</ul>
<p>&nbsp;</p>
<hr data-start="3662" data-end="3665" />
<h1 data-start="3667" data-end="3693"><strong data-start="3669" data-end="3693">Tools &amp; Technologies</strong></h1>
<p data-start="3695" data-end="3709"><strong data-start="3695" data-end="3709">Languages:</strong></p>
<ul data-start="3710" data-end="3744">
    <li data-start="3710" data-end="3718">
        <p data-start="3712" data-end="3718">Python</p>
    </li>
    <li data-start="3719" data-end="3731">
        <p data-start="3721" data-end="3731">JavaScript</p>
    </li>
    <li data-start="3732" data-end="3738">
        <p data-start="3734" data-end="3738">HTML</p>
    </li>
    <li data-start="3739" data-end="3744">
        <p data-start="3741" data-end="3744">CSS</p>
    </li>
</ul>
<p data-start="3746" data-end="3774"><strong data-start="3746" data-end="3774">Supporting Technologies:</strong></p>
<ul data-start="3775" data-end="3847">
    <li data-start="3775" data-end="3813">
        <p data-start="3777" data-end="3813">REST-style APIs / JSON data exchange</p>
    </li>
    <li data-start="3814" data-end="3847">
        <p data-start="3816" data-end="3847">MongoDB (subject to refinement)</p>
    </li>
</ul>
<p data-start="3849" data-end="3870"><strong data-start="3849" data-end="3870">Networking Tools:</strong></p>
<ul data-start="3871" data-end="3933">
    <li data-start="3871" data-end="3880">
        <p data-start="3873" data-end="3880">tcpdump</p>
    </li>
    <li data-start="3881" data-end="3897">
        <p data-start="3883" data-end="3897">ICMP utilities</p>
    </li>
    <li data-start="3898" data-end="3910">
        <p data-start="3900" data-end="3910">traceroute</p>
    </li>
    <li data-start="3911" data-end="3926">
        <p data-start="3913" data-end="3926">ARP utilities</p>
    </li>
    <li data-start="3927" data-end="3933">
        <p data-start="3929" data-end="3933">nmap</p>
    </li>
</ul>
<p data-start="3935" data-end="3948"><strong data-start="3935" data-end="3948">Platform:</strong></p>
<ul data-start="3949" data-end="3981">
    <li data-start="3949" data-end="3981">
        <p data-start="3951" data-end="3981">Local or self-hosted execution</p>
    </li>
</ul>
<hr data-start="3983" data-end="3986" />
<h1 data-start="3988" data-end="4027"><strong data-start="3990" data-end="4027">Testing Strategy (TBD)</strong></h1>
<ul data-start="4029" data-end="4286">
    <li data-start="4029" data-end="4076">
        <p data-start="4031" data-end="4076">Unit testing of discovery and inference logic</p>
    </li>
    <li data-start="4077" data-end="4144">
        <p data-start="4079" data-end="4144">Integration testing between scanning and visualization components</p>
    </li>
    <li data-start="4145" data-end="4182">
        <p data-start="4147" data-end="4182">Functional testing of core features</p>
    </li>
    <li data-start="4183" data-end="4236">
        <p data-start="4185" data-end="4236">Manual validation in small lab network environments</p>
    </li>
    <li data-start="4237" data-end="4286">
        <p data-start="4239" data-end="4286">Performance testing under varying device counts</p>
    </li>
</ul>
