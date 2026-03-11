# CA4

---

## Document Overview

**Subject:** Computer Architecture

**Summary:** This document provides an in-depth overview of exception and interrupt handling in the ARM processor. It covers the basics of exception handling, including ARM processor mode and exceptions, the vector table, exception priorities, and link register offsets. The document also delves into interrupts, discussing IRQ and FIQ interrupts, assigning interrupts, interrupt latency, IRQ and FIQ exceptions, and basic interrupt stack design and implementation. Furthermore, it explores various interrupt handling schemes used in the ARM processor, including nonnested, nested, reentrant, prioritized simple, prioritized standard, prioritized direct, and prioritized grouped interrupt handlers. The document concludes by highlighting the importance of understanding exceptions and interrupts in the ARM processor, including the distinction between interrupts and exceptions, and the typical uses of IRQ and FIQ exceptions.

**Core Topics:** Exception handling, Interrupts, Interrupt handling schemes, ARM processor modes, IRQ and FIQ exceptions, Interrupt latency, Vector Interrupt Controller (VIC), Nonnested interrupt handler, Nested interrupt handler, Reentrant interrupt handler, Prioritized simple interrupt handler, Prioritized standard interrupt handler, Prioritized direct interrupt handler, Prioritized grouped interrupt handler

**Chapters:**
  - **Exception and Interrupt Overview** (slides 1-1): exception handling, interrupts, interrupt handling schemes
  - **Exception Handling** (slides 2-2): ARM processor mode and exceptions, vector table, exception priorities, link register offsets
  - **Interrupts** (slides 3-3): assigning interrupts, interrupt latency, IRQ and FIQ exceptions, basic interrupt stack design and implementation
  - **Interrupt Handling Schemes** (slides 4-4): nonnested interrupt handler, nested interrupt handler, reentrant interrupt handler, prioritized simple interrupt handler, prioritized standard interrupt handler, prioritized direct interrupt handler, prioritized grouped interrupt handler, VIC PL190 based interrupt service routine
  - **Summary** (slides 5-5): exceptions, ARM processor modes, interrupts, interrupt latency, ISR


---

## Page 1

> **Title:** Exception and Interrupt Overview | **Type:** concept | **Concepts:** Exception handling, Interrupts, Interrupt handling schemes | **Chapter:** Exception and Interrupt Overview | **Exam Signal:** No
> **Summary:** This slide provides an overview of the document's content, introducing exception handling, interrupts as a special type of exception, and various interrupt handling schemes.

Exception and Interrupt

30-Jun-20
IIIT Naya Raipur

•Exception handling. Exception handling covers the specific details of 
how the ARM processor handles exceptions.
•Interrupts. ARM defines an interrupt as a special type of exception. 
This section discusses the use of interrupt requests, as well as 
introducing some of the common terms, features, and mechanisms 
surrounding interrupt handling.
•Interrupt handling schemes. The final section provides a set of 
interrupt handling methods. Included with each method is an 
example implementation.

---

## Page 2

> **Title:** Exception Handling | **Type:** concept | **Concepts:** ARM processor mode and exceptions, Vector table, Exception priorities, Link register offsets | **Chapter:** Exception Handling | **Exam Signal:** No
> **Summary:** This section outlines key topics related to exception handling, including ARM processor modes, vector tables, exception priorities, and link register offsets.

Exception Handling

•This section covers the following exception handling topics:
•ARM processor mode and exceptions
•Vector table
•Exception priorities
•Link register offsets

30-Jun-20
IIIT Naya Raipur

---

## Page 3

> **Title:** Interrupts | **Type:** concept | **Concepts:** Assigning interrupts, Interrupt latency, IRQ and FIQ exceptions, Basic interrupt stack design and implementation | **Chapter:** Interrupts | **Exam Signal:** No
> **Summary:** This section focuses on IRQ and FIQ interrupts, covering their assignment, interrupt latency, the nature of IRQ and FIQ exceptions, and basic interrupt stack design.

Interrupts

•In this section we will focus mainly on IRQ and FIQ interrupts. We will 
cover these topics:
•Assigning interrupts
•Interrupt latency
•IRQ and FIQ exceptions
•Basic interrupt stack design and implementation

30-Jun-20
IIIT Naya Raipur

---

## Page 4

> **Title:** Interrupt Handling Schemes | **Type:** concept | **Concepts:** Nonnested interrupt handler, Nested interrupt handler, Reentrant interrupt handler, Prioritized simple interrupt handler, Prioritized standard interrupt handler, Prioritized direct interrupt handler, Prioritized grouped interrupt handler, VIC PL190 based interrupt service routine | **Chapter:** Interrupt Handling Schemes | **Exam Signal:** No
> **Summary:** This slide details various interrupt handling schemes, including nonnested, nested, reentrant, and several prioritized handlers, along with a VIC PL190 based interrupt service routine.

Interrupt Handling Schemes

• The schemes covered are the following:
• ■ A nonnested interrupt handler handles and services individual interrupts sequentially. It is the 
simplest interrupt handler.
• ■ A nested interrupt handler handles multiple interrupts without a priority assignment.
• ■ A reentrant interrupt handler handles multiple interrupts that can be prioritized.
• ■ A prioritized simple interrupt handler handles prioritized interrupts.
• ■ A prioritized standard interrupt handler handles higher-priority interrupts in a shorter time than 
lower-priority interrupts.
• ■ A prioritized direct interrupt handler handles higher-priority interrupts in a shorter time and goes 
directly to a specific service routine.
• ■ A prioritized grouped interrupt handler is a mechanism for handling interrupts that are grouped 
into different priority levels.
• ■ A VIC PL190 based interrupt service routine shows how the vector interrupt controller (VIC) 
changes the design of an interrupt service routine

30-Jun-20
IIIT Naya Raipur

---

## Page 5

> **Title:** Summary | **Type:** summary | **Concepts:** Data Abort, Fast Interrupt Request, Interrupt Request, Prefetch Abort, Soft-ware Interrupt, Reset, Undefined Instruction, ARM processor mode, Interrupts, IRQ exception, FIQ exception, Interrupt latency, ISR | **Chapter:** Summary | **Exam Signal:** Yes
> **Summary:** This slide summarizes the seven types of exceptions and their associated ARM processor modes, defines interrupts, explains the roles of IRQ and FIQ exceptions, and clarifies interrupt latency.

Summary

• There are seven exceptions: Data Abort, Fast Interrupt Request, Interrupt Request, Prefetch Abort, Soft-ware Interrupt, Reset, and Undefined Instruction.
• Each exception has an associated ARM processor mode.
• Interrupts are a special type of exception that are caused by an external peripheral.
• The IRQ exception is used for general operating system activities.
• The FIQ exception is normally reserved for a single interrupt source.
• Interrupt latency is the interval of time from an external interrupt request signal being raised to the first fetch of an instruction of a specific interrupt service routine (ISR).
