# CA3

---

## Document Overview

**Subject:** Computer Architecture

**Summary:** This document provides an overview of the fundamental concepts of the ARM processor, focusing on its hardware components, instruction sets, and core extensions. The ARM processor features 16 data registers and 2 processor status registers, including special-purpose registers such as the stack pointer, link register, and program counter. The processor operates in three instruction sets: ARM, Thumb, and Jazelle, each with its own specific state. The ARM processor also has two interrupt request levels: IRQ and FIQ, which can be controlled by the interrupt mask bits in the CPSR. Additionally, the document discusses the core extensions, including caches, TCMs, memory management, and coprocessors, which enhance the processor's performance and functionality.

**Core Topics:** ARM processor, Registers, Instruction sets, Interrupt masks, Core extensions, Caches, TCMs, Memory management, Coprocessors

**Chapters:**
  - **Registers** (slides 1-1): data registers, processor status registers, special-purpose registers
  - **State and Instruction Sets** (slides 2-2): ARM instruction set, Thumb instruction set, Jazelle instruction set, processor state
  - **Interrupt Masks** (slides 3-3): interrupt request levels, cpsr interrupt mask bits, IRQ and FIQ
  - **Summary** (slides 4-4): ARM processor components, instruction sets, core extensions, memory management, coprocessors


---

## Page 1

> **Title:** Registers | **Type:** concept | **Concepts:** data registers, processor status registers, r0 to r15, stack pointer (sp), link register (lr), program counter (pc), r13, r14, r15, cpsr | **Chapter:** Registers | **Exam Signal:** No
> **Summary:** This slide describes the ARM processor's register set, including 16 data registers (r0-r15) and 2 processor status registers. It highlights special-purpose registers such as r13 for stack pointer, r14 for link register, and r15 for program counter.

Registers

16 data registers and 2 processor status registers. The data registers are visible to the programmer as r0 to r15.
The shaded registers identify the assigned special-purpose registers:

• Register r13 is traditionally used as the stack pointer (sp)
• Register r14 is called the link register (lr) and is where the core puts the return address whenever it calls a subroutine.
• Register r15 is the program counter (pc)

### Extracted from Image (OCR)

r10
r1l
r12
r13 sp
r14 Ir
r15 pc
cpsr

---

## Page 2

> **Title:** State and Instruction Sets | **Type:** concept | **Concepts:** ARM instruction set, Thumb instruction set, Jazelle instruction set, ARM state, Thumb state, 16-bit instructions, intermingle instructions | **Chapter:** State and Instruction Sets | **Exam Signal:** No
> **Summary:** The ARM processor supports three instruction sets: ARM, Thumb, and Jazelle, which are active depending on the processor's state. It is important to note that these instruction sets cannot be intermingled sequentially.

State and Instruction Sets

•There are three instruction sets: ARM, Thumb, and Jazelle.
• The ARM instruction set is only active when the processor is in ARM 
state. 
•Similarly the Thumb instruction set is only active when the processor is 
in Thumb state.
• Once in Thumb state the processor is executing purely Thumb 16-bit 
instructions. 
•You cannot intermingle sequential ARM, Thumb, and Jazelle 
instructions.

15-Jun-20
IIIT Naya Raipur

---

## Page 3

> **Title:** Interrupt Masks | **Type:** concept | **Concepts:** interrupt requests, interrupt request levels, IRQ, FIQ, cpsr interrupt mask bits, I bit, F bit | **Chapter:** Interrupt Masks | **Exam Signal:** No
> **Summary:** This slide details interrupt masks, which prevent specific requests from interrupting the processor, and identifies two interrupt request levels: IRQ and FIQ. The cpsr contains mask bits (I and F) that control the masking of IRQ and FIQ respectively.

Interrupt Masks

• To stop specific interrupt requests from interrupting the processor.

• There are two interrupt request levels available on the ARM processor 
core—interrupt request (IRQ) and fast interrupt request (FIQ).

• The cpsr has two interrupt mask bits, 7 and 6 (or I and F), which control the 
masking of IRQ and FIQ, respectively.

• The I bit masks IRQ when set to binary 1, and similarly the F bit masks FIQ when 
set to binary 1.

15-Jun-20
IIIT Naya Raipur

---

## Page 4

> **Title:** Summary | **Type:** summary | **Concepts:** ARM processor fundamentals, ALU, barrel shifter, MAC, register file, instruction decoder, address register, incrementer, sign extend, ARM instruction set, Thumb instruction set, Jazelle instruction set, core extensions, Caches, TCMs, Memory management, Coprocessors, Coprocessor 15 | **Chapter:** Summary | **Exam Signal:** Yes
> **Summary:** This slide provides a summary of ARM processor fundamentals, outlining its eight core components, three instruction sets (ARM, Thumb, Jazelle), and various core extensions like caches, TCMs, memory management, and coprocessors.

Summary

• Hardware fundamentals of the actual ARM processor.
• The ARM processor can be abstracted into eight components—ALU, barrel shifter, MAC, register file, instruction decoder, address register, incrementer, and sign extend.
• ARM has three instruction sets—ARM, Thumb, and Jazelle.
• The core extensions include the following:
• Caches are used to improve the overall system performance.
• TCMs are used to improve deterministic real-time response.
• Memory management is used to organize memory and protect system resources.
• Coprocessors are used to extend the instruction set and functionality. Coprocessor 15 controls the cache, TCMs, and memory management.

15-Jun-20
IIIT Naya Raipur
