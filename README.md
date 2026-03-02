<h2 data-start="234" data-end="247"><span style="font-size: 36pt;">NetTower - Capstone</span></h2>
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
<h1 data-start="3208" data-end="3238"><strong data-start="3210" data-end="3238">Timeline:</strong></h1>
<ul data-start="3463" data-end="3660">
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprints 1 &amp; 2 (Subject to adjustments)</p>
    </li>
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprint 1<br />Phase Date Focus<br />S1W1 (Week 5 &ndash; 2/9) Project setup and baseline agentless discovery<br />S1W2 (Week 6 &ndash; 2/16) Network scanning and host identification<br />S1W3 (Week 7 &ndash; 2/23) Basic connectivity inference and relationship modeling<br />S1W4 (Week 8 &ndash; 3/2) Backend Completion &amp; Stability</p>
    </li>
</ul>
<p>Sprint 1 Presentation (3/2)</p>
<ul data-start="3463" data-end="3660">
    <li data-start="3636" data-end="3660">
        <p data-start="3638" data-end="3660">Sprint 2<br />Phase Date Focus<br />S2W1 (Week 10 &ndash; 3/16) Building Front End<br />S2W2 (Week 11 &ndash; 3/23) Refinement of front end and Visual enhancement<br />S2W3 (Week 12 &ndash; 3/30) Frontend&ndash;Backend Integration &amp; Topology Rendering<br />S2W4 (Week 13 &ndash; 4/6) Performance Optimization &amp; System Refinement + User Testing<br />S2W5 (Week 14 &ndash; 4/13) Documentation and publication prep<br />S2W6 (Week 15 &ndash; 4/20) Final testing, demo, and submission</p>
    </li>
</ul>
<p>Week 16 (4/27) Final Presentation</p>
<p>&nbsp;</p>
<h3 data-start="554" data-end="583"><strong data-start="557" data-end="583">Milestones &amp; Deadlines</strong></h3>
<h4 data-start="271" data-end="308">Milestone 1 &ndash; February 16, 2026</h4>
<p data-start="2151" data-end="2194">Planning &amp; Backend Architecture Finalized</p>
<h4 data-start="351" data-end="388">Hard Deadline 1 &ndash; March 9, 2026</h4>
<p data-start="2241" data-end="2288">Backend Core Complete (Sprint 1 Presentation)</p>
<h4 data-start="421" data-end="455">Milestone 2 &ndash; March 24, 2026</h4>
<p data-start="1230" data-end="1263">Frontend Integration Functional</p>
<h4 data-start="493" data-end="530">Hard Deadline 2 &ndash; April 7, 2026</h4>
<p data-start="2015" data-end="2077">Functional Prototype Ready (Backend + Initial Visualization)</p>
<h4 data-start="566" data-end="600">Milestone 3 &ndash; April 14, 2026</h4>
<p data-start="1412" data-end="1451">Visualization Enhancements Integrated</p>
<h4 data-start="647" data-end="685">Hard Deadline 3 &ndash; April 17, 2026</h4>
<p data-start="686" data-end="717">Refinement &amp; Testing Complete</p>
<h4 data-start="724" data-end="758">Milestone 4 &ndash; April 19, 2026</h4>
<p data-start="759" data-end="790">Documentation &amp; Demo Prepared</p>
<h4 data-start="797" data-end="832">Hard Deadline 4 &ndash; April 22, 2026</h4>
<p data-start="833" data-end="856">Finalized &amp; Published</p>
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
<p data-start="4288" data-end="4390">&nbsp;</p>
<hr data-start="4392" data-end="4395" />
<h1 data-start="4397" data-end="4419"><strong data-start="4399" data-end="4419">Learning with AI</strong></h1>
<h3 data-start="4421" data-end="4440">Topics to Learn</h3>
<ul data-start="4441" data-end="4586">
    <li data-start="4441" data-end="4521">
        <p data-start="4443" data-end="4521">Layer 2, Layer 3, and Layer 4 protocol behavior, limitations, and capabilities</p>
    </li>
    <li data-start="4522" data-end="4586">
        <p data-start="4524" data-end="4586">Traffic packet structure and protocol breakdown at a low level</p>
    </li>
</ul>
<h3 data-start="4588" data-end="4606">How AI Is Used</h3>
<ul data-start="4607" data-end="4822">
    <li data-start="4607" data-end="4654">
        <p data-start="4609" data-end="4654">Breaking down protocol mechanics step-by-step</p>
    </li>
    <li data-start="4655" data-end="4698">
        <p data-start="4657" data-end="4698">Exploring inference limits and edge cases</p>
    </li>
    <li data-start="4699" data-end="4760">
        <p data-start="4701" data-end="4760">Supporting design decisions for discovery and visualization</p>
    </li>
    <li data-start="4761" data-end="4822">
        <p data-start="4763" data-end="4822">Validating reasoning about constrained network environments</p>
    </li>
</ul>
<p data-start="4824" data-end="4914">The AI component supports technical learning rather than adding AI-based product features.</p>
<hr data-start="4916" data-end="4919" />
<h1 data-start="4921" data-end="4945"><strong data-start="4923" data-end="4945">Challenges / Risks</strong></h1>
<ul data-start="4947" data-end="5226">
    <li data-start="4947" data-end="4986">
        <p data-start="4949" data-end="4986">Incomplete or misleading network data</p>
    </li>
    <li data-start="4987" data-end="5036">
        <p data-start="4989" data-end="5036">Inferring relationships without full visibility</p>
    </li>
    <li data-start="5037" data-end="5088">
        <p data-start="5039" data-end="5088">Representing uncertainty clearly in visualization</p>
    </li>
    <li data-start="5089" data-end="5130">
        <p data-start="5091" data-end="5130">Balancing simplicity with useful detail</p>
    </li>
    <li data-start="5131" data-end="5179">
        <p data-start="5133" data-end="5179">Reaching segmented or restricted network areas</p>
    </li>
    <li data-start="5180" data-end="5226">
        <p data-start="5182" data-end="5226">Managing time alongside military obligations</p>
    </li>
</ul>
<hr data-start="5228" data-end="5231" />
<h1 data-start="5233" data-end="5255"><strong data-start="5235" data-end="5255">Publication Plan</strong></h1>
<p data-start="5257" data-end="5570">NetTower will be published as a web-based project page documenting the system&rsquo;s purpose, design decisions, capabilities, and limitations. The source code and documentation will be made publicly available through a GitHub repository, and example visualizations will be included to demonstrate system functionality.</p>
