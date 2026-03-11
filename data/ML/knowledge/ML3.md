# ML3

---

## Document Overview

**Subject:** Machine Learning

**Summary:** Gradient descent is a first-order iterative optimization algorithm used to find a local minimum of a differentiable function. The algorithm works by taking steps proportional to the negative of the gradient of the function at the current point, with the goal of moving towards the minimum on the error surface. The learning rate plays a crucial role in the algorithm, as a rate that is too small can lead to slow convergence, while a rate that is too large can cause overshooting or divergence. The gradient descent algorithm is applied in linear regression, and monitoring its effectiveness is crucial. This is achieved by plotting the cost function J(θ) to check if it decreases with every iteration. If not, the learning rate needs to be reduced. However, a too small learning rate can lead to slow convergence.

**Core Topics:** Gradient descent, Local minimum, Differentiable function, Steepest descent, Cost function, Mean-squared error, Gradient of the error surface, learning rate, convergence, overshooting, divergence, Gradient Descent Algorithm, Univariate Linear Regression, Linear Regression Model, plotting the cost function J(θ), learning rate adjustment

**Chapters:**
  - **Gradient Descent Basics** (slides 1-1): Gradient descent, Steepest descent, Cost function, Mean-squared error, Gradient of the error surface
  - **The Learning Rate** (slides 2-2): Learning rate, Convergence, Step size adjustment, Choosing the learning rate
  - **Gradient Descent Algorithm** (slides 3-3): Gradient descent algorithm, Univariate linear regression, Table 1
  - **Monitoring Gradient Descent** (slides 4-4): Monitoring J(θ), Convergence, Learning rate adjustment


---

## Page 1

> **Title:** Gradient Descent Basics (slides 1-1) | **Type:** definition | **Concepts:** Gradient descent, Steepest descent, optimization algorithm, local minimum, cost function, mean-squared error, error surface, gradient | **Chapter:** Gradient Descent Basics | **Exam Signal:** No
> **Summary:** Gradient descent is a first-order iterative optimization algorithm designed to find a local minimum of a differentiable function. It operates by taking steps proportional to the negative gradient of the function, using a cost function like mean-squared error to move towards the minimum on the error surface.

Gradient/Steepest descent

Gradient descent is a first-order iterative optimization algorithm for 
finding a local minimum of a differentiable function.

To find a local minimum of a function using gradient descent, we take 
steps proportional to the negative of the gradient (or approximate 
gradient) of the function at the current point.

• Define cost function as mean-squared error
• Difference between estimated output and actual target value
• Based on the method of steepest descent
• Move towards the minimum on the error surface to get to 
minimum
• Requires the gradient of the error surface to be known

---

## Page 2

> **Title:** The Learning Rate (slides 2-2) | **Type:** concept | **Concepts:** learning rate, convergence, step size, alpha (α), local minimum, overshoot, diverge | **Chapter:** The Learning Rate | **Exam Signal:** No
> **Summary:** The learning rate (α) influences the convergence of gradient descent, and while it doesn't always need to change over time, its value must be chosen carefully. A learning rate that is too small results in slow convergence, whereas one that is too large can cause the algorithm to overshoot the minimum, fail to converge, or even diverge.

The learning rate

• Do we need to change learning rate over time?
o No, Gradient descent can converge to a local

minimum, even with the learning rate α fixed
o Step size adjusted automatically

• But, value needs to be chosen judiciously
o If α is too small, gradient descent can be slow to

converge
o If α is too large, gradient descent can overshoot the

minimum. It may fail to converge, or even diverge.

---

## Page 3

> **Title:** Gradient Descent Algorithm (slides 3-3) | **Type:** table | **Concepts:** Gradient descent algorithm, univariate linear regression, Table 1, repeat until convergence, J(θ0, θ1) | **Chapter:** Gradient Descent Algorithm | **Exam Signal:** No
> **Summary:** This slide presents the gradient descent algorithm specifically for univariate linear regression, including "Table 1" which illustrates the iterative process and components, such as the cost function J(θ0, θ1), repeated until convergence.

Gradient descent algorithm
Linear Regression Model

Gradient descent for
univariate linear regression

### Table 1

| repeat | until | convergence |
| --- | --- | --- |
| ∂ |  |  |
| Ql | J(θ0, θ1) |  |
| ∂θj |  |  |
| (for j | = 1 and j = ( | 0) |

---

## Page 4

> **Title:** Monitoring Gradient Descent (slides 4-4) | **Type:** concept | **Concepts:** J(θ), monitoring, iteration, convergence, learning rate, slow convergence | **Chapter:** Monitoring Gradient Descent | **Exam Signal:** No
> **Summary:** To ascertain if gradient descent is working correctly, one should plot the change in J(θ) with each iteration; J(θ) should consistently decrease for a sufficiently small learning rate. If J(θ) does not decrease, the learning rate needs to be reduced, though a very small learning rate can lead to slow convergence.

Is gradient descent working properly?

• Plot how J(θ) changes with every iteration of 
gradient descent

• For sufficiently small learning rate, J(θ) should 
decrease with every iteration

• If not, learning rate needs to be reduced

• However, too small learning rate means slow 
convergence
