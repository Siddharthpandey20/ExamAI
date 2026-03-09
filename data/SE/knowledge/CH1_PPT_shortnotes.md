# CH1_PPT_shortnotes

---

## Document Overview

**Subject:** Software Engineering

**Summary:** Software engineering is the application of a systematic, disciplined, and quantifiable approach to developing, operating, and maintaining software. The field has faced challenges such as the software crisis, characterized by failed projects, late delivery, and high costs. To overcome these limitations, software engineering techniques such as abstraction, decomposition, and structured programming have been developed. The field has evolved from exploratory style problem-solving to modern software development practices, which involve using life cycle models to ensure a common understanding among developers and make project management possible. The classical waterfall model is a simple and intuitive life cycle model that consists of phases such as feasibility study, requirements analysis and specification, design, coding and unit testing, integration and system testing, and maintenance. The field also categorizes software into different types, including generic/product software, custom software, horizontal market software, vertical market software, and software services. Overall, software engineering is a systematic approach to developing software that involves using techniques such as abstraction, decomposition, and structured programming, and following a life cycle model to ensure successful software development.

**Core Topics:** Software Engineering, Systematic Approach, Software Crisis, Exploratory Style Problem, Abstraction, Decomposition, Structured Programming, Life Cycle Model, Software Development Life Cycle (SDLC), Feasibility Study, Requirements Analysis & Specification, Design, Coding & Unit Testing, Integration & System Testing, Maintenance, Phase Entry & Exit Criteria, Milestones, Software Categories, Generic/Product Software, Custom Software, Horizontal Market Software, Vertical Market Software, Software Services, Computer Systems Engineering

**Chapters:**
  - **What is Software Engineering?** (slides 1-1): Software Engineering, IEEE Definition, Systematic Approach
  - **Challenges in Software Engineering** (slides 2-2): Unmaintainable Code, Fails in Team Development, Human Cognitive Limitation, Effort Grows Exponentially
  - **Early Software Engineering Techniques** (slides 3-3): Data Structure-Oriented Design, JSP, Warnier-Orr Methodology
  - **Modern Software Engineering Practices** (slides 4-4): Error Prevention, Error Correction, Life Cycle Model, SDLC
  - **Software Engineering Life Cycle Models** (slides 5-5): Requirements Analysis & Specification, Design, Coding & Unit Testing, Integration & System Testing, Maintenance, Waterfall Model
  - **Software Categories** (slides 6-6): Generic Software, Product Software, Custom Software
  - **Exam Questions and Answers** (slides 7-7): Software Engineering Definition, Software Crisis, Abstraction and Decomposition


---

## Page 1

> **Title:** What is Software Engineering? | **Type:** concept | **Concepts:** Software Engineering, IEEE Definition, Systematic Approach, Software Crisis, Standish Group Report, Exploratory Style, Build-and-Fix Style, Exponential Effort | **Chapter:** What is Software Engineering? (slides 1-1) | **Exam Signal:** Yes
> **Summary:** This slide defines Software Engineering as a systematic, disciplined approach to software development, introduces the "Software Crisis" with its causes and statistics from the Standish Group Report, and discusses the inefficiency of the "Exploratory Style" where effort grows exponentially.

SOFTWARE ENGINEERING

B.Tech 2nd Year — Exam Ready Notes 
Unit 1: Introduction to SE + Life Cycle Models

1. What is Software Engineering?

IEEE Definition: "The application of a systematic, disciplined, quantifiable approach to the development, 
operation, and maintenance of software." 
 
Simply: It's the engineering approach to build software — using systematic techniques instead of guesswork.

• 
Uses past experience, methodologies, guidelines 
• 
Think of it like Building Construction — structured, planned, not random 
 
💡 Analogy: Just like a building needs blueprints and construction phases, software needs design docs and SDLC 
phases.

2. Software Crisis

In early days, software projects often:

• 
Failed to meet user requirements 
• 
Were expensive and delivered late 
• 
Were difficult to maintain, debug, or change 
• 
Used resources non-optimally 
 
Key Stat (Standish Group Report):

Outcome 
Percentage

Successful 
28%

Delayed / Cost Overrun 
49%

Cancelled 
23%

Causes of Software Crisis: Larger problem sizes, poor project management, lack of SE training, skill shortage, low 
productivity improvements. 
 
💡 Remember: Software crisis = projects fail due to lack of engineering discipline, NOT because of hardware 
problems.

3. Why Not Just Code? — The Exploratory Style Problem

Exploratory (Build-and-Fix) Style

Early programmers wrote code first, fixed bugs as they appeared. Works only for very small / toy programs.

• 
Code → Test → Fix → Repeat (until done) 
• 
Effort grows EXPONENTIALLY with program size (not linearly!)

### Table 1

|  | •  Were expensive and delivered late |  |
| --- | --- | --- |
|  | •  Were difficult to maintain, debug, or change |  |
|  | • 
Used resources non-optimally |  |
| K | ey Stat (Standish Group Report): |  |
|  | Outcome | Percentage |
|  | Successful | 28% |
|  | Delayed / Cost Overrun | 49% |
|  | Cancelled | 23% |
| C | auses of Software Crisis: Larger problem sizes, poor project management, lack of SE training, skill shortage, low |  |
| productivity improvements. |  |  |

---

## Page 2

> **Title:** Challenges in Software Engineering | **Type:** concept | **Concepts:** Unmaintainable Code, Team Development, Human Cognitive Limitation, Magical Number 7, Abstraction, Decomposition, Model Building, Hierarchy of Abstractions, Software Design Techniques, Control Flow-Based Design, Structured Programming | **Chapter:** Challenges in Software Engineering (slides 2-2) | **Exam Signal:** Yes
> **Summary:** This slide explains why software development effort grows exponentially due to human cognitive limitations, exemplified by "The Magical Number 7," and introduces fundamental SE techniques like "Abstraction" and "Decomposition" to manage complexity. It also begins the evolution of software design techniques, starting with Control Flow-Based Design.

• 
Results in unmaintainable code 
• 
Fails completely in team development

Why does effort grow exponentially?

Human cognitive limitation — The Magical Number 7 (Miller, 1956):

• 
Short-term memory holds ≤ 7 items at a time 
• 
As variables/modules in a program grow beyond 7, understanding it becomes very hard 
• 
Chunking helps (grouping related info) but only partially 
 
💡 Exam Point: Effort grows exponentially because human short-term memory is limited. SE techniques fight 
this via Abstraction & Decomposition.

4. Two Fundamental SE Techniques

Technique 
What it Means

Abstraction 
Simplify by omitting unnecessary details. Focus on one 
aspect, ignore the rest. Example: Map of a country 
instead of visiting every house.

Decomposition 
Break a big problem into small, independent parts. Solve 
each separately. Example: Break sticks individually, not 
as a bunch.

These techniques directly overcome human cognitive limitations and keep effort-vs-size curve nearly LINEAR 
instead of exponential.

• 
Abstraction = Model Building (multiple abstractions of same problem possible) 
• 
Decomposition = parts must be independent of each other 
• 
Complex problems may need a hierarchy of abstractions (e.g., Kingdom → Phylum → Species)

5. Evolution of Software Design Techniques

Design techniques evolved in response to increasing program size and complexity:

Era / Technique 
Key Idea

1950s — Assembly Language 
Exploratory/build-and-fix style. Programs limited to few 
hundred lines.

Early 60s — High-Level Languages 
FORTRAN, ALGOL, COBOL. Reduced effort but style was 
still exploratory.

Late 60s — Control Flow-Based Design 
Focus on program's control structure. Flow charts 
introduced. Dijkstra's 'GOTO Considered Harmful' (1969). 
Only 3 constructs needed: Sequence, Selection, Iteration 
→ Structured Programming.

### Table 1

| 4. Two Fundamental SE Techniques |  |
| --- | --- |
| Technique | What it Means |
| Abstraction | Simplify by omitting unnecessary details. Focus on one |
|  | aspect, ignore the rest. Example: Map of a country |
|  | instead of visiting every house. |
| Decomposition | Break a big problem into small, independent parts. Solve |
|  | each separately. Example: Break sticks individually, not |
|  | as a bunch. |

---

## Page 3

> **Title:** Modern Software Engineering Practices | **Type:** comparison | **Concepts:** Data Structure-Oriented Design, JSP, Warnier-Orr Methodology, Data Flow-Oriented Design, DFDs, Object-Oriented Design, Component-Oriented, Service-Oriented, Aspect-Oriented, Structured Programming, Sequence, Selection, Iteration, GOTO, Exploratory Style, Modern SE Practices, Error Prevention, Error Correction | **Chapter:** Modern Software Engineering Practices (slides 4-4) | **Exam Signal:** Yes
> **Summary:** This slide continues tracing the evolution of software design techniques, details "Structured Programming" and its advantages, and contrasts "Exploratory Style" with "Modern Software Development Practices," emphasizing a shift from error correction to error prevention.

Era / Technique 
Key Idea

Early 70s — Data Structure-Oriented 
Design

Program structure derived from data structure. JSP 
(Jackson Structured Programming) by Michael Jackson. 
Also Warnier-Orr methodology.

Late 70s — Data Flow-Oriented Design 
Identify input data → processing → output data. Uses 
DFDs (Data Flow Diagrams). Simple, generic, works for 
any system.

80s — Object-Oriented Design 
Natural objects (employees, payroll) identified first. 
Relationships: composition, inheritance, reference. Data 
hiding/encapsulation.

Modern — Component/Service/Aspect-
Oriented

Reuse of components, service-based architecture.

💡 Memory Trick: Control → Data Structure → Data Flow → Object Oriented (C-D-D-O) — chronological order 
of design evolution!

Structured Programming — Key Exam Topic

A program is STRUCTURED if it uses ONLY:

• 
Sequence — e.g., a=0; b=5; 
• 
Selection — e.g., if-else 
• 
Iteration — e.g., while, for 
• 
Consists of modules (no GOTO) 
 
Advantages of Structured Programming:

• 
Easier to read and understand 
• 
Easier to maintain 
• 
Less time and effort to develop 
• 
Less bugs 
 
GOTO was proven UNNECESSARY — any logic can be expressed with just sequence + selection + iteration.

6. Exploratory Style vs. Modern Software Development

Exploratory Style 
Modern SE Practices

Errors detected only during testing 
Errors detected in every phase, ASAP

Coding = entire program development 
Coding is just a small part of development

No formal design phase 
Distinct requirements + design phases

No documentation 
Good documentation at every stage

No reviews or metrics 
Periodic reviews, metrics, CASE tools

No project planning 
Estimation, scheduling, monitoring

### Table 1

| Errors detected only during testing 
Errors detected in every phase, ASAP |
| --- |
| Coding = entire program development 
Coding is just a small part of development |
| No formal design phase 
Distinct requirements + design phases |
| No documentation 
Good documentation at every stage |
| No reviews or metrics 
Periodic reviews, metrics, CASE tools 
No project planning 
Estimation, scheduling, monitoring |

---

## Page 4

> **Title:** Software Engineering Life Cycle Models | **Type:** definition | **Concepts:** Life Cycle Model, SDLC, Process Model, Feasibility Study, Requirements Analysis & Specification, Design, Coding & Unit Testing, Integration & System Testing, Maintenance, Phase Entry Criteria, Exit Criteria, Milestones, Classical Waterfall Model | **Chapter:** Software Engineering Life Cycle Models (slides 5-5) | **Exam Signal:** Yes
> **Summary:** This slide defines the Software Life Cycle Model (SDLC), outlines its phases and importance for systematic development and project management, and introduces the Classical Waterfall Model, detailing its first phase: Feasibility Study.

Exploratory Style 
Modern SE Practices

Works for toy programs only 
Works for large, complex, team projects

💡 Key Shift: Modern SE shifted from Error Correction to Error Prevention — catch bugs early, not after they 
spread!

7. Life Cycle Model (SDLC)

What is a Life Cycle Model?

• 
A descriptive & diagrammatic model of software development 
• 
Identifies all activities, establishes their order, divides work into phases 
• 
Also called: Process Model / SDLC 
 
Phases of Software Life Cycle:

• 
Feasibility Study 
• 
Requirements Analysis & Specification 
• 
Design 
• 
Coding & Unit Testing 
• 
Integration & System Testing 
• 
Maintenance

Why Use a Life Cycle Model?

• 
Ensures common understanding among developers 
• 
Helps identify inconsistencies, redundancies, omissions in process 
• 
Allows systematic, disciplined development 
• 
Makes project management possible (track progress at any time) 
• 
Without it → 99% Complete Syndrome (manager can't tell true progress)

Phase Entry & Exit Criteria

Every phase has Entry Criteria (what must be true to START) and Exit Criteria (what must be true to END). 
Example: SRS phase exit = SRS document complete, reviewed, and approved by customer. 
Milestones = Phase entry/exit points — used by project managers to track progress. 
 
💡 Exam Question: 'What is the deliverable/exit criteria for Phase X?' — Know at least the SRS exit criteria.

8. Classical Waterfall Model

Simplest and most intuitive life cycle model. Phases flow downward like a waterfall.

Phase 
Key Activity / Output

1. Feasibility Study 
Is the project technically & financially viable? Cost-
benefit analysis.

### Table 1

| 7. Life Cycle Model (SDLC) |  |  |
| --- | --- | --- |
| What is a Life Cycle Model? |  |  |
|  | • | A descriptive & diagrammatic model of software development |
|  | • | Identifies all activities, establishes their order, divides work into phases |
|  | • | Also called: Process Model / SDLC |
| P | hases of Software Life Cycle: |  |
|  | • | Feasibility Study |
|  | • | Requirements Analysis & Specification |
|  | • | Design |
|  | • | Coding & Unit Testing |
|  | • | Integration & System Testing |
|  | •  Maintenance |  |

---

## Page 5

> **Title:** Software Engineering Life Cycle Models | **Type:** concept | **Concepts:** Classical Waterfall Model, Requirements Analysis & Specification, SRS document, Design documents, Coding & Unit Testing, Integration & System Testing, Maintenance, Effort Distribution, Feasibility Study, Technical Feasibility, Economic Feasibility, Schedule Feasibility, Cost-Benefit Analysis (CBA) | **Chapter:** Software Engineering Life Cycle Models (slides 5-5) | **Exam Signal:** Yes
> **Summary:** This slide elaborates on the remaining phases of the Classical Waterfall Model and discusses the significant effort distribution across development and maintenance. It also details the three dimensions of "Feasibility Study" (technical, economic, schedule) and the process of "Cost-Benefit Analysis."

Phase 
Key Activity / Output

2. Requirements Analysis & Specification 
Understand what customer wants → SRS document

3. Design 
Structured design, data design → Design documents

4. Coding & Unit Testing 
Write code, test individual modules

5. Integration & System Testing 
Combine modules, test the full system

6. Maintenance 
Bug fixes, enhancements post-deployment

Effort Distribution (Important!)

• 
Maintenance phase = Maximum effort among ALL phases 
• 
Testing phase = Maximum effort among DEVELOPMENT phases 
• 
Development phases = everything from feasibility study to testing

9. Feasibility Study

Three Dimensions of Feasibility

Type 
Meaning

Technical Feasibility 
Can it be built with available technology and skills?

Economic Feasibility 
Are benefits greater than costs? (Cost-Benefit Analysis)

Schedule Feasibility 
Can it be built within the required timeframe?

Cost-Benefit Analysis (CBA)

• 
Identify all costs: Development + Setup + Operational 
• 
Identify benefits: Quantifiable (money saved) + Non-quantifiable (reputation) 
• 
Benefits must outweigh costs → Go decision 
• 
If no solution is feasible (too costly, technical constraints) → No-Go

Activities in Feasibility Study

• 
Get overall understanding of the problem 
• 
Formulate different solution strategies 
• 
Examine each alternative (resources, cost, time) 
• 
Perform CBA to pick the best solution 
• 
Present findings → Go/No-Go decision

10. Types of Software & Projects

### Table 1

| Phase | Key Activity / Output |
| --- | --- |
| 2. Requirements Analysis & Specification | Understand what customer wants → SRS document |
| 3. Design | Structured design, data design → Design documents |
| 4. Coding & Unit Testing | Write code, test individual modules |
| 5. Integration & System Testing | Combine modules, test the full system |
| 6. Maintenance | Bug fixes, enhancements post-deployment |

---

## Page 6

> **Title:** Software Categories | **Type:** summary | **Concepts:** Generic Software, Product Software, Custom Software, Horizontal Market Software, Vertical Market Software, Software Services, Computer Systems Engineering, Hardware/Software Partitioning, Software Engineering, SDLC, Structured Programming, Abstraction, Decomposition, Feasibility Study, Milestone, Design Technique Evolution | **Chapter:** Software Categories (slides 6-6) | **Exam Signal:** Yes
> **Summary:** This slide categorizes different types of software and projects, introduces Computer Systems Engineering for combined hardware-software products, and provides a "Quick Revision — Exam Cheat Sheet" summarizing key definitions and the historical evolution of design techniques.

Category 
Description

Generic / Product Software 
Developed for mass market (horizontal or vertical). e.g., 
MS Office

Custom Software 
Built for specific client's request. Tailored solution.

Horizontal Market Software 
Meets needs of many companies across industries

Vertical Market Software 
Designed for a particular industry only

Software Services 
Customization, maintenance, testing, contract 
programming

Modern Trend: Projects are increasingly services-based — reuse existing code/libraries, incremental delivery, 
client feedback during development.

11. Computer Systems Engineering

When a product needs BOTH hardware and software (e.g., coffee vending machine, robotic toy):

• 
Computer systems engineering = software engineering + hardware engineering 
• 
Key decision: Which tasks done by hardware vs software? 
• 
Hardware and software developed together (hardware simulator used during SW dev) 
• 
Phases: Feasibility → Requirements → Hardware/Software Partitioning → Parallel Development → 
Integration & Testing

⚡ Quick Revision — Exam Cheat Sheet

Key Definitions to Write in Exam:

• 
Software Engineering (IEEE): Systematic, disciplined, quantifiable approach to development, operation & 
maintenance of software. 
• 
SDLC: Descriptive model identifying all activities, their order, and phases of software development. 
• 
Structured Programming: Program using only sequence, selection, iteration — no GOTO. 
• 
Abstraction: Simplifying a problem by focusing on relevant aspects and ignoring details. 
• 
Decomposition: Breaking a large problem into small, independent sub-problems. 
• 
Feasibility Study: Initial phase to determine if project is economically & technically viable. 
• 
Milestone: A significant event in a project (usually phase entry/exit) used to track progress. 
 
Design Technique Evolution (timeline):

• 
1950s: Exploratory/Ad hoc 
• 
Late 60s: Control flow → Structured Programming (GOTO harmful, Dijkstra 1969) 
• 
Early 70s: Data Structure-Oriented (JSP by Michael Jackson) 
• 
Late 70s: Data Flow-Oriented (DFDs) 
• 
80s: Object-Oriented (encapsulation, inheritance) 
• 
Modern: Component / Service / Aspect Oriented

### Table 1

| Category | Description |
| --- | --- |
| Generic / Product Software | Developed for mass market (horizontal or vertical). e.g., |
|  | MS Office |
| Custom Software | Built for specific client's request. Tailored solution. |
| Horizontal Market Software | Meets needs of many companies across industries |
| Vertical Market Software | Designed for a particular industry only |
| Software Services | Customization, maintenance, testing, contract |
|  | programming |

### Table 2

| 11. Computer Systems Engineering |  |
| --- | --- |
| When a product needs BOTH hardware and software (e.g., coffee vending machine, robotic toy): |  |
| • | Computer systems engineering = software engineering + hardware engineering |
| • | Key decision: Which tasks done by hardware vs software? |
| • | Hardware and software developed together (hardware simulator used during SW dev) |
| • | Phases: Feasibility → Requirements → Hardware/Software Partitioning → Parallel Development → |
|  | Integration & Testing |

---

## Page 7

> **Title:** Exam Questions and Answers | **Type:** summary | **Concepts:** Waterfall Model Phases, Feasibility, Requirements Analysis, Design, Coding & Unit Testing, Integration & System Testing, Maintenance, Software Engineering Definition, Software Crisis, Abstraction, Decomposition, Structured Programming, Software Design Techniques, Life Cycle Model, Classical Waterfall Model, Feasibility Study, Exploratory Style, Modern SE Practices, Magical Number 7 | **Chapter:** Exam Questions and Answers (slides 7-7) | **Exam Signal:** Yes
> **Summary:** This slide concludes the "Exam Cheat Sheet" with a list of Waterfall Model phases and presents a comprehensive list of "Most Likely Exam Questions" covering fundamental concepts discussed throughout the document.

Waterfall Model Phases (in order):

• Feasibility → Requirements Analysis → Design → Coding & Unit Testing → Integration & System Testing → Maintenance

Most Likely Exam Questions:

• Define Software Engineering. What is the Software Crisis?
• Explain Abstraction and Decomposition with examples.
• What is Structured Programming? What are its advantages?
• Describe the evolution of software design techniques.
• What is a Life Cycle Model? Why is it needed?
• Explain Classical Waterfall Model with phases and diagram.
• What is Feasibility Study? What are its three dimensions?
• Difference between Exploratory style and Modern SE practices.
• What is the Magical Number 7 and how does it relate to SE?
