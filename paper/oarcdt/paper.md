---
title: 'OSDT-MEDUSA, an extension for Open Spatial Digital Twin'
tags:
  - digital twin
  - stormwater
  - pollution
  - spatial
  - geospatial
  
authors:
  - name: Casey Li
    orcid: 0009-0009-1707-8289
    equal-contrib: true 
    affiliation: "1, 2"

  - name: Luke Parkinson
    orcid: 0000-0003-3130-3445
    equal-contrib: true 
    affiliation: 1
    
  - name: Xander Cai
    orcid: 0009-0008-9995-9778
    affiliation: 1
  
  - name: Martin Nguyen
    orcid: 0000-0003-4469-0149
    affiliation: 1

  - name: Matthew Wilson
    orcid: 0000-0001-9459-6981
    affiliation: 1
    
  - name: Greg Preston
    affiliation: 2
  
  - name: Sam
    affiliation: 3
  - name: todo others as needed
    
affiliations:
  - name: Geospatial Research Institute | Toi Hangarau, New Zealand
    index: 1
  - name: Building Innovation Partnership, New Zealand
    index: 2
  - name: Auckland todo
    index: 3

date: 17 October 2024
bibliography: paper_oarcdt.bib
---
[@todo] Matt notes -- Use this as a case study, and focus on the OARCDT. Also describe how our changes have impacted the core digital twin by creating a modular framework to allow for more domains. cut out core digital things as much as possible


# Summary
Why the Ōtākaro is in need of a digital twin...

How our implementation fills that need...

What our digital twin is and what it enables..... (brief)

How the Ōtākaro implementation is gives mana to the Ōtākaro...

How this impacted the core of the digital twin project (give this project a name)

Overview of the digital twin project evolving from FReDT, to an open-source framework.


There is a lack of open-source solutions to geospatial digital twins [@todo] provide reference


# Background
[@todo] Introduce our digital twin framework...
The Open Spatial Digital Twin (OSDT) is a software framework for building geospatial environmental digital twins [@OSDT]. It began as the Flood Resilience Digital Twin [@FREDT, @FREDT-JOSS], before developing into a modular framework capable of being extended into multiple environmental domains through plugin-style extensions, and interoperability with other spatial digital twins and services.

The Ōtākaro/Avon River Corridor (ŌARC) in Christchurch, New Zealand is undergoing significant development as part of the ŌARC Regeneration Plan (ref). It is an initiative by central government (?) and Christchurch City Council (CCC) to restore the health of the river, and bring people back as part of the recovery after the 2011-20XX Christchurch Earthquake Sequence. [@todo] tie this back to the language found in the council documents

After the earthquakes, XX households were displaced...

The OARC Regeneration will... (revitalise wetlands, recreation areas, water treatment, biodiversity etc.)

To aid in decision making CCC is making use of (DigitalTwinFramework)


# Statement of need
#### Current situation
* Stormwater pollution produces these negative outcomes....
* The ŌARC is unhealthy...
#### What is the problem?
* Limited ability to understand health of river...
* Limited public understanding of pollutant sources...
* Limited public understanding of what they can do to fix it
* Difficult for council to model, so siloed knowledge into small teams.
*
#### Why is it not solved?
* The difficulty of spatial modelling ...
* Multi domain is difficult...
* limited public educational resources that are engaging...
* 
#### How to solve it
* Modelling the sources of these pollutions via MEDUSA is effective because...
* It allows us to effect positive change by ... (democratising, etc.)
* Using a digital twin is great because...
* Making it open source can help other communities by...


# Aim
[@todo] XANDER's notes - provide more context about exactly what we have built, so it does not come across as fluff that has little real world impact
[@todo] Cut down on this aim

Establish an accessible and innovative platform, to collect and communicate knowledge about the Ōtākaro River, serving as a tool to give voice to the Ōtākaro and its importance to the community. 

The platform aims to foster collaboration to support and encourage: 

* Holistic decision making & governance. 
* Environmental health and resilience outcomes 
* Representation of the mauri of the Ōtākaro and; 
* Amplify the significance of the Ōtākaro to the region and people by allowing users to model potential future narratives and tell stories of the Ōtākaro’s past & present. 

The Ōtākaro Digital Twin purpose is guided by the Te Mana o te Wai framework and aims to be adaptable to other locations and environments. 


# Modular plugins framework
[@todo]Discuss modifying FReDT into a modular framework that can act across many domains
A framework for open-source digital twin with modular ecosystems allows...
- Benefits
- Open Source and closed source examples
- Make it clear the plugin was created for CCC, to fit into our new modular framework.

# Case study
 CCC needed a module for pollution. The first implementation of this module focuses on modelling pollutant sources from storm events based on MEDUSA 2.0 [@medusa, @todo] describe.
 
 * Some ideas on why it is appropriate and important for MEDUSA module to be open-source

* How the MEDUSA module can be applied to other environments.... (some work may be required to code this correctly (think about adjusting the inputs via a catalog means or something similar, and the security impacts therein.))


# Data analysis
* Medusa as a plugin

* Use as Web-Processing-Service or Web-Map-Service within existing analysis workflows.

* Ability to compare our MEDUSA implementation to other closed-source implementations. AND/OR how our implementation accuracy is similar.
* Why our implentation may be advantageous over closed-source versions?

[@todo Have some additional thoughts about QGIS WPS plugin, and if that is worth mentioning

# Acknowledgements
* CCC
* GRI
* BIP
* UC
* NTRC
* CreateBig
* WSP
* OpenPlan
* Ngāi Tūāhuriri
* Pounamu Ngāi Tahu
* [@todo]todo

# References
