# ML-03-linear-regression

---

## Document Overview

**Subject:** Statistics

**Summary:** Regression analysis is a statistical method used to establish a relationship between dependent and independent variables. It is a powerful tool for modeling and predicting continuous outcomes. The lecture notes cover the fundamental concepts and techniques of regression analysis, including: 

**Core Topics:** regression analysis, simple linear regression, multiple linear regression, assumptions of regression analysis, model building and evaluation, advanced topics in regression analysis

**Chapters:**
  - **Introduction to Regression Analysis** (slides Page 1-3): Regression analysis, Linear regression, Non-linear regression
  - **Non-Linear Transformations** (slides Page 4-12): Logarithmic transformation, Square-root transformation, Reciprocal transformation
  - **Coefficient of Determination (R^2)** (slides Page 13-16): R^2, Explained variation, Unexplained variation
  - **Bias-Variance Trade-Off** (slides Page 17-23): Bias, Variance, Irreducible error, Model selection
  - **Examples** (slides Page 24-26): Linear regression, Non-linear regression, Model selection


---

## Page 1

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Regression, Simple Linear Regression, Multiple Regression, Definition, Model Training, Coefficient Estimation, Gradient descent method, Least square method, Polynomial Regression, Multi-collinearity | **Exam Signal:** No
> **Summary:** This slide provides an overview of regression analysis, covering various topics such as simple and multiple linear regression, model training, coefficient estimation methods like gradient descent and least squares, polynomial regression, and multi-collinearity.

Regression

•
Simple Linear Regression & Multiple Regression
•
Definition and Model Training
•
Coefficient Estimation: Gradient descent method, least square method
•
Polynomial Regression
•
Multi-collinearity in Regression

---

## Page 2

> **Title:** Introduction to Regression Analysis | **Type:** definition | **Concepts:** Linear regression, Linear model, Simple linear regression, Multiple linear regression, Least Squares | **Exam Signal:** No
> **Summary:** This slide reviews linear regression as a model assuming a linear relationship between input and output variables, defining simple linear regression for a single input and multiple linear regression for multiple inputs, with Least Squares as a common training method.

Linear Regression: 
Quick Review

• Linear regression is a linear model, e.g. a model that assumes a linear relationship
between the input variables (x) and the single output variable (y).

• More specifically, that y can be calculated from a linear combination of the input
variables (x).

• When there is a single input variable (x), the method is referred to as simple
linear regression.

• When there are multiple input variables, literature from statistics often refers to
the method as multiple linear regression.

• Different techniques can be used to train the linear regression model (equation)
from data, the most common of which is called Least Squares. It is common to
therefore refer to a model prepared this way as Least Squares Linear Regression.

---

## Page 3

> **Title:** Introduction to Regression Analysis | **Type:** definition | **Concepts:** Linear Regression Model Representation, Linear equation, Input values (x), Output values (y), Coefficient (Beta), Intercept, Bias coefficient | **Exam Signal:** No
> **Summary:** This slide explains the linear regression model representation as a linear equation that combines input values to predict output, assigning coefficients (Beta) to each input and an additional intercept or bias coefficient for line adjustment.

Linear Regression Model Representation

• The representation is a linear equation that combines a specific set of input values (x) which is used to predict output values (y). As such, both the input values (x) and the output value are numeric.

• The linear equation assigns one scale factor to each input value, called a coefficient that is commonly represented by the Greek letter Beta (β). One additional coefficient is also added, giving the line an additional degree of freedom (e.g. moving up and down on a two-dimensional plot) and is often called the intercept or the bias coefficient. For example,

y = B0 + B1 x1 +……

intercept/bias
Coefficient
---

### Table 1

| Linear Regression Model Representation |
| --- |
| • The representation is a linear equation that combines a specific set of |
| input values (x) which is used to predict output values (y). As such, |
| both the input values (x) and the output value are numeric. |
| • The linear equation assigns one scale factor
to each input
value, |
| called a coefficient that is commonly represented by the Greek letter |
| Beta (β). One additional coefficient
is also added, giving the line an |
| additional degree of
freedom (e.g. moving up and down on a two- |
| dimensional
plot)
and
is
often
called
the
intercept
or
the
bias |
| coefficient. For example, |
| y = B0 + B1 x1 +……. |
| intercept/bias
Coefficient |

---

## Page 4

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Assumptions: Linear Regression Model, Linearity, Homoscedasticity, Predictor (X) | **Exam Signal:** No
> **Summary:** This slide outlines key assumptions for linear regression models: linearity, requiring a linear relationship between variables, and homoscedasticity, which mandates constant variance around the regression line for all predictor values, illustrated with a figure showing a violation.

Assumptions: Linear Regression Model

• Linearity: The relationship between the two variables is linear.
• Homoscedasticity: The variance around the regression line is the same for all values of X (predictor). A clear violation of this assumption is shown in below Figure.

### Extracted from Image (OCR)

3.5
2.5
2.5
3.5
High School GPA

---

## Page 5

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Assumptions, Remove Collinearity, Gaussian Distributions, Errors of prediction, Rescale Inputs, Standardization, Normalization, Normal Distribution of errors | **Exam Signal:** No
> **Summary:** This slide discusses additional assumptions for linear regression, emphasizing the removal of collinearity, the assumption of normally distributed prediction errors, and the importance of rescaling input variables via standardization or normalization for reliable predictions.

Assumptions

• Remove Collinearity: It will not work when you have highly correlated input variables. Consider calculating pairwise correlations for your input data and removing the most correlated.
• Gaussian Distributions: The errors of prediction are distributed normally: This means that the deviations from the regression line are normally distributed.
• Rescale Inputs: Linear regression will often make more reliable predictions if you rescale input variables using standardization or normalization.

### Extracted from Image (OCR)

Normal Distribution of errors
Price
Area
Y=Price of the house and X=Area of the house

---

## Page 6

> **Title:** Introduction to Regression Analysis | **Type:** syntax/code | **Concepts:** Simple Regression, Coefficient Estimation, hθ(x), θ0, θ1, β1, β0 | **Exam Signal:** No
> **Summary:** This slide presents the mathematical formulas for coefficient estimation in simple regression, including the hypothesis function hθ(x) and the equations for calculating β1 and β0.

Simple Regression: Coefficient Estimation

### Extracted from Image (OCR)

hθ(x) = θ0 + θ1x
Already Done
Home Work
∑i=1( − x)( − y)
m
β1 =
∑ m=1 ( − x)2$
m
βo = − β1x

---

## Page 7

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Linear, Non-Linear, CGPA, Hours, muscle power, age | **Exam Signal:** No
> **Summary:** This slide visually distinguishes between linear and non-linear relationships using scatter plots, illustrating how variables like CGPA vs. Hours and muscle power vs. age can display different patterns.

Linear

Non-Linear

### Extracted from Image (OCR)

CGPA
Hours
muscle power
age
muscle power
age
CGPA
Hours

---

## Page 8

> **Title:** Introduction to Regression Analysis | **Type:** example | **Concepts:** Multiple or Multi-variate Regression, Independent variable, Area of house, Number of bed rooms, Price | **Exam Signal:** No
> **Summary:** This slide introduces multiple or multi-variate regression, defining it as a model with more than one independent variable. It provides an example with house area and number of bedrooms influencing price, along with the assumed regression equation.

Multiple or Multi-variate Regression

When there are more than one independent variable

### Table 1

| Area of house in | Number of bed | Price in lakhs |
| --- | --- | --- |
| square foot | rooms |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
| Assumed |  |  |
| Price = θ0 + θ1 * Area + θ2 * Number of bed rooms |  |  |
| No. Bed |  |  |
| oms |  |  |
| Area |  |  |

---

## Page 9

> **Title:** Introduction to Regression Analysis | **Type:** definition | **Concepts:** Multiple Regression Equation, Y-hat, β0 (y-intercept), β1 (slope), βP (slope), ε (error) | **Exam Signal:** No
> **Summary:** This slide defines the multiple regression equation (Y-hat = β0 + β1x1 + ... + βPxP + ε), explaining β0 as the y-intercept and β1 through βP as the slopes of Y with respect to their respective variables, holding others constant.

Multiple Regression Equation

Y-hat = β0 + β1x1 + β2x2 + ... + βPxP + ε

where:
  
β0 = y-intercept  {a constant value}

β1 = slope of Y with variable x1 holding the

variables x2, x3, ..., xP effects  constant
  
βP = slope of Y with variable xP holding all      
other variables’ effects constant

---

## Page 10

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Multi-variate Regression, Coefficient estimation, Least square estimation, Matrix method, Gradient descent | **Exam Signal:** No
> **Summary:** This slide explains that coefficient estimation in multi-variate regression is complex, noting that least square estimation and matrix methods can be used for 'p' independent variables, with gradient descent being a better, scalable option for higher 'p' values.

Multi-variate Regression: Coefficient estimation

When there are more than one independent variables

• Estimation is complex as compared to simple regression
• Least square estimation can be used
• For p number of independent variables, matrix method can be used to find the solution
• For much higher value of p, gradient descent is a better option due to its scalable feature

---

## Page 11

> **Title:** Introduction to Regression Analysis | **Type:** diagram_explanation | **Concepts:** Plotting multivariate data, 3D Scatter plot, Sepal.Length | **Exam Signal:** No
> **Summary:** This slide illustrates the plotting of multivariate data using a 3D scatter plot, showing an example with variables labeled 'x', 'Position', and 'Sepal.Length' to visualize relationships between three dimensions.

Plotting multivariate data: 3D Scatter plot

### Extracted from Image (OCR)

x
Position
x
4.
4.0
3.5
3.0
2.5
2.0
Sepal.Length

---

## Page 12

> **Title:** Non-Linear Transformations | **Type:** definition | **Concepts:** Polynomial Regression, Non-linear relationship, Age, Salary in thousands, Predicted value, Dependent variable, Independent variable | **Exam Signal:** No
> **Summary:** This slide introduces polynomial regression as a method for modeling non-linear relationships between variables, illustrating that the predicted dependent variable is not a straight-line function of the independent variable, such as Age versus Salary.

Polynomial Regression

• When there is no linear relationship between variables

### Extracted from Image (OCR)

Age
Salary in thousands
Polynomial regression
×
×
SseeaM
(x) Age
The predicted value of dependent variable is not a straight-line function of
independent variable

---

## Page 13

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Polynomial regression, Linear relation, Age, Salary | **Exam Signal:** No
> **Summary:** This slide visually contrasts a linear fit with a polynomial regression fit for data where the relationship between Age and Salary is non-linear, emphasizing that polynomial regression allows for a non-straight-line prediction of the dependent variable.

### Extracted from Image (OCR)

Polynomial regression
×
×
×
×
×
x
x
x
×x
(y)
(x) Age
Salary = θ + θ1 * Age
If we fit a linear relation
Polynomial regression
x
x
×
x
x
x
x
×
x
(y)
x
(x) Age
The predicted value of dependent variable is not a straight-line function of
independent variable

---

## Page 14

> **Title:** Non-Linear Transformations | **Type:** example | **Concepts:** Polynomial regression, Degree of polynomial, Age, Salary, Salary = θ0 + θ1 * Age + θ2 * Age* Age | **Exam Signal:** No
> **Summary:** This slide addresses the challenge of choosing the correct polynomial degree by presenting an example table of Age and Salary data, alongside an equation for a second-degree polynomial regression.

How to choose the right degree of polynomial?

### Table 1

| Age | Salary in | Age |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Polynomial regression | thousan | Age |  |  |  |  |  |  |  |  |
| ds |  |  |  |  |  |  |  |  |  |  |
| × | × | × | x | × | × | × x | × | × | × | × |
| × |  |  |  |  |  |  |  |  |  |  |
| ×× |  |  |  |  |  |  |  |  |  |  |
| (y) |  |  |  |  |  |  |  |  |  |  |
| × |  |  |  |  |  |  |  |  |  |  |
| (x) Age |  |  |  |  |  |  |  |  |  |  |
| Salary = θ0 + θ1 * Age + θ2 * Age* Age |  |  |  |  |  |  |  |  |  |  |

---

## Page 15

> **Title:** Non-Linear Transformations | **Type:** concept | **Concepts:** Degree of polynomial, Forward selection, Backward selection, t-test, Number of bumps in curve, Scatter plot | **Exam Signal:** No
> **Summary:** This slide outlines strategies for selecting the appropriate degree of a polynomial, including forward selection by testing coefficient significance, backward selection by deleting highest-order terms, and counting the number of bumps in a scatter plot for large datasets.

How to choose the right degree of polynomial?

### Extracted from Image (OCR)

Forward selection: One possible approach is to successively fit the models in
increasing order and test the significance of regression coefficients at each step of
model fitting. Keep the order increasing until t-test for the highest order term is
non-significant.
Backward selection: Another approach is to fit the appropriate highest order
model and then delete terms one at a time starting with highest order. This is
continued until the highest order remaining term has a significant t-statistic.
Number of bumps in curve: This approach is useful when you have large data set
and independent variables are not correlated. Draw scatter plot with dependent
variable on Y axis and independent variable on X axis. Count the number of
bumps. Degree of polynomial should number of bumps plus one

---

## Page 16

> **Title:** Non-Linear Transformations | **Type:** concept | **Concepts:** Multivariate Case, Degree, Regularization, Ridge, Elastic Net, Cross-validation, Feature selection, Domain knowledge, Interactions | **Exam Signal:** No
> **Summary:** This slide provides practical strategies for multivariate polynomial regression, recommending keeping the degree small, using strong regularization like Ridge or Elastic Net, preferring cross-validation, considering feature selection, and incorporating domain knowledge for meaningful interactions.

Practical Strategy for Multivariate Case

• Keep degree small (2 or 3)
• Use strong regularization (Ridge / Elastic Net)
• Prefer cross-validation
• Consider feature selection
• Use domain knowledge to include only meaningful interactions

---

## Page 17

> **Title:** Introduction to Regression Analysis | **Type:** definition | **Concepts:** Multi-collinearity in Regression, Independent variables, Correlation, Coefficient estimation, Relationship between independent and dependent variables | **Exam Signal:** No
> **Summary:** This slide defines multi-collinearity as the correlation among independent variables in regression and explains its problematic nature, stating it makes coefficient estimation and interpretation of individual variable relationships difficult.

Multi-collinearity in Regression

• When independent variables in regression are correlated
• Why this is problematic
• If the degree of correlation between variables is high enough, it can cause problems when you fit the model and interpret the results
• The stronger the correlation, the more difficult it is to change one variable without changing another
• It becomes difficult for the model to estimate the relationship between each independent variable and the dependent variable independently

---

## Page 18

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Structural multi-collinearity, Data multi-collinearity, Model term, Curvature, Observational experiments, Multichannel ECG | **Exam Signal:** No
> **Summary:** This slide differentiates between structural multi-collinearity, which arises from the model specification (e.g., squaring a term), and data multi-collinearity, which is inherently present in the dataset, often found in observational experiments.

Types

• Structural multi-collinearity: This type occurs when we create a model term using other terms. In other words, it’s a byproduct of the model that we specify rather than being present in the data itself.

• For example, if you square term X to model curvature, clearly there is a correlation between X and X^2.
• Data multi-collinearity: This type of multi-collinearity is present in the data itself rather than being an artifact of our model.

• Observational experiments are more likely to exhibit this kind of multi-collinearity.
• E.g, multichannel ECG
---

---

## Page 19

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Impact of Multi-collinearity, Coefficient estimates, Statistical power, p-values, Statistically significant | **Exam Signal:** No
> **Summary:** This slide outlines the negative impacts of multi-collinearity on regression, including unstable coefficient estimates, sensitivity to model changes, reduced statistical power, and unreliable p-values for identifying statistically significant independent variables.

Impact of Multi-collinearity on Regression

• The coefficient estimates can swing wildly based on which other independent variables are in the model.
• The coefficients become very sensitive to small changes in the model.
• Multi-collinearity reduces the precision of the estimated coefficients, which weakens the statistical power of your regression model.
• You might not be able to trust the p-values to identify independent variables that are statistically significant.

---

## Page 20

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Handle multi-collinearity, Severity, Moderate multicollinearity, Variables in interest | **Exam Signal:** No
> **Summary:** This slide explains that the decision to handle multi-collinearity depends on its severity and the regression model's objective, suggesting that moderate multicollinearity or situations where variables of interest are not correlated may not necessitate resolution.

Need to handle multi-collinearity

• The need to reduce multi-collinearity depends on its severity and your 
primary goal for your regression model
• The severity of the problems increases with the degree of the 
multicollinearity.

• Therefore, if you have only moderate multicollinearity, you may not need to resolve it.
• Multicollinearity affects only the specific independent variables that are 
correlated.

• Therefore, if the variables in interest are not correlated, you may not need to resolve 
it.

---

## Page 21

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Handle multi-collinearity, Remove correlated independent variables, Linearly combine independent variables, Principal components analysis, Partial least squares regression, LASSO regression, Ridge regression | **Exam Signal:** No
> **Summary:** This slide lists several methods to address multi-collinearity, including removing or combining highly correlated independent variables, performing specialized analyses like principal components or partial least squares regression, and utilizing advanced regression techniques such as LASSO and Ridge regression.

How to handle multi-collinearity?

• Remove some of the highly correlated independent variables.
• Linearly combine the independent variables, such as adding them 
together.
• Perform an analysis designed for highly correlated variables, such as 
principal components analysis or partial least squares regression.
• LASSO and Ridge regression are advanced forms of regression analysis 
that can handle multicollinearity. If you know how to perform linear 
least squares regression, you’ll be able to handle these analyses with 
just a little additional study.

---

## Page 22

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Measure Multi-collinearity, Correlation Test, Variance Inflation Factor (VIF), VIF values | **Exam Signal:** No
> **Summary:** This slide details methods for measuring multi-collinearity, including the Correlation Test and the Variance Inflation Factor (VIF), explaining that VIF values between 1 and 5 suggest moderate correlation, while values greater than 5 indicate critical multicollinearity.

How to measure Multi-collinearity?

• The simplest one is Correlation Test
• There is another very simple test to assess multicollinearity in your regression model.
• The variance inflation factor (VIF) identifies correlation between independent variables and the strength of that correlation.
• VIFs start at 1 and have no upper limit.
• A value of 1 indicates that there is no correlation between this independent variable and any others.
• VIFs between 1 and 5 suggest that there is a moderate correlation, but it is not severe enough to warrant corrective measures.
• VIFs greater than 5 represent critical levels of multicollinearity where the coefficients are poorly estimated, and the p-values are questionable.

### Extracted from Image (OCR)

VIFj
=
1 −

---

## Page 23

> **Title:** Bias-Variance Trade-Off | **Type:** concept | **Concepts:** Statistical Tests, F test, t-test, Significant relationship, Individual significance | **Exam Signal:** No
> **Summary:** This slide explains the F test, used to determine if a significant relationship exists between the dependent variable and the set of all independent variables, and the t-test, conducted for each independent variable to assess individual significance.

Statistical Tests

• The F test is used to determine whether a significant relationship exists between the dependent variable and the set of all the independent variables.
• A separate t-test is conducted for each of the independent variables in the model. We refer to each of these t tests as a test for individual significance.

---

## Page 24

> **Title:** Bias-Variance Trade-Off | **Type:** comparison | **Concepts:** Testing for Significance, Simple linear regression, Multiple regression, F test, t tests | **Exam Signal:** No
> **Summary:** This slide compares the F and t tests for significance, noting that they yield the same conclusion in simple linear regression but serve different purposes in multiple regression.

In simple linear regression, the F and t tests provide the same conclusion.

Testing for Significance

In multiple regression, the F and t tests have different purposes.

### Table 1

| Testing for Significance |
| --- |
| In simple linear regression, the F and t tests provide |
| the same conclusion. |
| In multiple regression, the F and t tests have different |
| purposes. |

---

## Page 25

> **Title:** Examples | **Type:** definition | **Concepts:** Dummy/Indicator-Variable Regression, Dummy variable, Categorical effect, Qualitative facts, Mutually exclusive categories | **Exam Signal:** No
> **Summary:** This slide defines dummy or indicator variables as numeric values (0 or 1) used in regression to represent the absence or presence of categorical effects. They act as stand-ins for qualitative facts, sorting data into mutually exclusive categories.

Dummy/Indicator-Variable Regression

Model

A dummy variable is one that takes only the value 0 or 1 to indicate the absence or presence of some categorical effect that may be expected to shift the outcome
• They can be thought of as numeric stand-ins for qualitative facts in a regression model, sorting data into mutually exclusive categories (such as smoker and non-smoker).
• Involves categorical X variable with two levels
• e.g., female-male, employed-not employed, etc.
---

### Table 1

| Dummy/Indicator-Variable Regression |
| --- |
| Model |
| A dummy variable is one that takes only the value 0 or |
| 1 to indicate the absence or presence of some |
| categorical effect that may be expected to shift the |
| outcome |
| • They can be thought of as numeric stand-ins for |

---

## Page 26

> **Title:** Examples | **Type:** table | **Concepts:** Qualitative independent variables, Experience Score, Degree, Salary | **Exam Signal:** No
> **Summary:** This slide presents a table showing data for qualitative independent variables, including experience score, graduate degree status, and salary.

24.0
43.0
23.7
34.3
35.8
38.0
22.2
23.1
30.0
33.0

38.0
26.6
36.2
31.6
29.0
34.0
30.1
33.9
28.2
30.0

Exper. Score
Score
Exper.
Salary
Salary
Degr.

No
Yes
 No
Yes
Yes
Yes
 No
 No
 No
Yes

Degr.

Yes
 No
Yes
 No
 No
Yes
 No
Yes
 No
 No

Examp: Qualitative Independent Variables

### Table 1

| Examp: Qualitative Independent Variables |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  | Exper. Score |  | Degr. | Salary |  | Exper. | Score | Degr. | Salary |
|  |  |  | No | 24.0 |  |  |  | Yes | 38.0 |
|  |  |  | Yes | 43.0 |  |  |  | No | 26.6 |
|  |  |  | No | 23.7 |  |  |  | Yes | 36.2 |
|  |  |  | Yes | 34.3 |  |  |  | No | 31.6 |
|  |  |  | Yes | 35.8 |  |  |  | No | 29.0 |
|  |  |  | Yes | 38.0 |  |  |  | Yes | 34.0 |
|  |  |  | No | 22.2 |  |  |  | No | 30.1 |
|  |  |  | No | 23.1 |  |  |  | Yes | 33.9 |
|  |  |  | No | 30.0 |  |  |  | No | 28.2 |
|  |  |  | Yes | 33.0 |  |  |  | No | 30.0 |

---

## Page 27

> **Title:** Examples | **Type:** definition | **Concepts:** Dummy variable, Regression equation, Annual salary, Years of experience, Programmer aptitude test score, Graduate degree | **Exam Signal:** No
> **Summary:** This slide defines a regression equation with a dummy variable, explaining how it codes for the presence or absence of a graduate degree in relation to annual salary.

Example: Dummy Variable

y = b0 + b1x1 + b2x2 + b3x3

^
where:

y = annual salary ($1000)
  x1 = years of experience
  x2 = score on programmer aptitude test
  x3 = 0 if individual does not have a graduate degree
          1 if individual does have a graduate degree

x3 is a dummy variable

How it will change the Regression/Fittet Line/Model?

Variable levels coded 0 & 1

### Table 1

| y = b0 + b1x1 + b2x2 + b3x3 |
| --- |
| where: |
| ^ |
| y = annual salary ($1000) |
| x1 = years of experience |
| x2 = score on programmer aptitude test |
| x3 = 0 if individual does not have a graduate degree |
| 1 if individual does have a graduate degree |

---

## Page 28

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Dummy-variable regression model, Categorical X variable, Variable levels coded 0 & 1, Intercept difference, Constant slopes | **Exam Signal:** No
> **Summary:** This slide describes the Dummy-Variable Regression Model, highlighting its use with categorical independent variables with two levels coded as 0 and 1, assuming only the intercept differs between categories.

Dummy-Variable Regression Model

• Involves categorical X variable with 
two levels

• e.g., female-male, employed-not employed, etc.
• Variable levels coded 0 & 1
• Assumes only intercept is different
• When 1, Slopes are constant across categories
• When 0, such variables have no role in influencing the DV

### Table 1

| Dummy-Variable Regression Model |
| --- |
| • Involves categorical X variable with |
| two levels |
| • e.g., female-male, employed-not employed, etc. |
| • Variable levels coded 0 & 1 |
| • Assumes only intercept is different |
| • When 1, Slopes are constant across categories |
| • When 0, such variables have no role in influencing the DV |

---

## Page 29

> **Title:** Introduction to Regression Analysis | **Type:** diagram_explanation | **Concepts:** Dummy-variable model relationships, Same slopes, Intercept b0, Intercept b0 + b2, Females, Males | **Exam Signal:** No
> **Summary:** This slide illustrates Dummy-Variable Model Relationships, showing two parallel regression lines for different categories (Females and Males) with the same slope but different intercepts.

Dummy-Variable Model Relationships

Y

X1


Same slopes b1

b0

b0 + b2

Females

Males

### Table 1

| Dummy-Variable Model Relationships |
| --- |
| Y |
| Same slopes b1 |
| Females |
| b0 + b2 |
| b0 |
| Males |
|  |
| X1 |
|  |

---

## Page 30

> **Title:** Introduction to Regression Analysis | **Type:** definition | **Concepts:** Interaction regression model, Interaction between pairs of X variables, Two-way cross product terms, Y = β0 + β1x1 + β2x2 + β3x1x2 + ε, Dummy variable models | **Exam Signal:** No
> **Summary:** This slide defines the Interaction Regression Model, explaining that it hypothesizes interactions between independent variables, where the response to one variable varies at different levels of another.

Interaction Regression Model

• Hypothesizes interaction between pairs of X variables

• Response to one X variable varies at different levels of another X variable

• Contains two-way cross product terms

Y = β0 + β1x1 + β2x2 + β3x1x2 + ε

• Can be combined with other models e.g. dummy variable models

### Table 1

| Interaction Regression Model |
| --- |
| • Hypothesizes interaction between pairs of X |
| variables |
| • Response to one X variable varies at different levels of |
| another X variable |
| • Contains two-way cross product terms |
| Y = 0 + 1x1 + 2x2 + 3x1x2 +   |
| • Can be combined with other models |
| e.g. dummy variable models |

---

## Page 31

> **Title:** Introduction to Regression Analysis | **Type:** concept | **Concepts:** Effect of interaction, Interaction term, Effect of X1 on Y, β1, β1 + β3X2 | **Exam Signal:** No
> **Summary:** This slide explains the effect of an interaction term in a regression model, showing how the influence of X1 on Y changes from β1 to β1 + β3X2 when an interaction term is present.

Effect of Interaction

• Given:
  • Without interaction term, effect of X1 on Y is measured by β1
  • With interaction term, effect of X1 on Y is measured by β1 + β3X2
  • Effect increases as X2i increases

X
X
X
X
Y
ε
β
β
β
β
+
+
+
+
=

### Table 1

|  |  | Effect of Interaction |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| • Given: |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Y | = |  | + |  | X |  | + |  | X |  |  | + |  | X |  | X |  |  | +
 |  |
| i |  |  |  |  |  | 1
i |  |  |  |  | i |  |  |  | 1
i |  |  | i |  | i |
| • Without interaction term, effect of X1 on Y is measured by 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| • With interaction term, effect of X1 on |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | Y is measured by 1 + 3X2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | • Effect increases as X2i increases |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

---

## Page 32

> **Title:** Examples | **Type:** example | **Concepts:** Interaction example, Y = 1 + 2X1 + 3X2 + 4X1X2 | **Exam Signal:** No
> **Summary:** This slide presents an interaction example using the equation Y = 1 + 2X1 + 3X2 + 4X1X2 and a graphical representation with X1 values.

Interaction Example

X1
0.5
1.5

Y = 1 + 2X1 + 3X2 + 4X1X2

### Table 1

|  | Interaction Example |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | Y = 1 + 2X1 + 3X2 + 4X1X2 |  |  |
|  | Y |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | X1 |
|  |  | 0.5 |  | 1.5 |  |

---

## Page 33

> **Title:** Examples | **Type:** numerical_example | **Concepts:** Interaction example, Effect of X1, Y = 1 + 2X1 + 3X2 + 4X1X2, Y = 1 + 2X1 | **Exam Signal:** No
> **Summary:** This slide continues the interaction example, demonstrating the effect of X1 on Y when X2 is set to 0, resulting in the simplified equation Y = 1 + 2X1.

Interaction Example: Effect of X1

X1





0.5
1.5

Y

Y = 1 + 2X1 + 3X2 + 4X1X2

Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1
---

No changes were made to the original text, as per the absolute rules.

### Table 1

| Interaction Example: Effect of X1 |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | Y = 1 + 2X1 + 3X2 + 4X1X2 |  |  |
|  | Y |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  | Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1 |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | X1 |
|  |  | 0.5 |  | 1.5 |  |

---

## Page 34

> **Title:** Examples | **Type:** numerical_example | **Concepts:** Interaction example, Y = 1 + 2X1 + 3X2 + 4X1X2, Y = 4 + 6X1, Y = 1 + 2X1 | **Exam Signal:** No
> **Summary:** This slide further demonstrates the interaction example by showing the derived equations for Y when X2 is 0 (Y = 1 + 2X1) and when X2 is 1 (Y = 4 + 6X1).

Interaction Example

Y

X1





0.5
1.5

Y = 1 + 2X1 + 3X2 + 4X1X2

Y = 1 + 2X1 + 3(1) + 4X1(1) = 4 + 6X1

Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1
---

### Table 1

|  | Interaction Example |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | Y = 1 + 2X1 + 3X2 + 4X1X2 |  |  |
|  | Y |  |  |  |  |
|  |  |  | Y = 1 + 2X1 + 3(1) + 4X1(1) = 4 + 6X1 |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  | Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1 |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | X1 |
|  |  | 0.5 |  | 1.5 |  |

---

## Page 35

> **Title:** Examples | **Type:** diagram_explanation | **Concepts:** Interaction example, Effect of X1 on Y depends on X2 value, Y = 4 + 6X1, Y = 1 + 2X1 | **Exam Signal:** No
> **Summary:** This slide concludes the interaction example by stating that the effect (slope) of X1 on Y depends on the value of X2, illustrating this with two different equations derived when X2 is 0 and 1.

Interaction Example

Effect (slope) of X1 on Y does depend on X2 value

X1





0.5
1.5

Y

Y = 1 + 2X1 + 3X2 + 4X1X2

Y = 1 + 2X1 + 3(1) + 4X1(1) = 4 + 6X1

Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1

### Table 1

|  | Interaction Example |  |  |  |  |
| --- | --- | --- | --- | --- | --- |
|  |  |  | Y = 1 + 2X1 + 3X2 + 4X1X2 |  |  |
|  | Y |  |  |  |  |
|  |  |  | Y = 1 + 2X1 + 3(1) + 4X1(1) = 4 + 6X1 |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  | Y = 1 + 2X1 + 3(0) + 4X1(0) = 1 + 2X1 |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  |  |
|  |  |  |  |  | X1 |
|  |  | 0.5 |  | 1.5 |  |
|  | Effect (slope) of X1 on Y does depend on X2 value |  |  |  |  |

---

## Page 36

> **Title:** Non-Linear Transformations | **Type:** concept | **Concepts:** Non-linear transformation, Non-linear least square | **Exam Signal:** No
> **Summary:** This slide introduces non-linear transformations and mentions that implementing them directly involves non-linear least squares, which can be complex and time-consuming.

Non-Linear Transformation

What if I want to implement it as it is? 
Non-linear least square! a bit complex, time taking

### Table 1

| Non-Linear Transformation |
| --- |
| What if I want to implement it as it is? |
| Non-linear least square! a bit complex, time taking |

---

## Page 37

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Logarithmic transformation, Y = β + β1 ln(x1) + β2 ln(x2) + ε, β1 > 0, β1 < 0 | **Exam Signal:** No
> **Summary:** This slide illustrates the Logarithmic Transformation, showing a regression equation involving natural logarithms of independent variables and a graph depicting the effect of positive and negative β1.

Logarithmic Transformation

Y

X1

β1 > 0

β1 < 0

Y = β + β1 ln(x1) + β2 ln(x2) + ε

### Table 1

| Logarithmic Transformation |  |
| --- | --- |
| Y =   + 1 lnx1 + 2 lnx2 +   |  |
| Y |  |
| 1 > 0 |  |
| 1 < 0 |  |
|  | X1 |

---

## Page 38

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Square-root transformation, Y = β + β1√X1 + β2√X2 + ε, β1 > 0, β1 < 0 | **Exam Signal:** No
> **Summary:** This slide presents the Square-Root Transformation, including its regression equation and a graph showing the different trends for positive and negative β1.

Square-Root Transformation

Y

X1

i
i
i
i
X
X
Y
ε
β
β
β
+
+
+
=

β1 > 0

β1 < 0

### Table 1

| Square-Root Transformation |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Y | = |  | + |  | X |  | + |  | X |  |  | +
 |  |
| i |  |  |  |  |  | 1
i |  |  |  |  | i |  | i |
| Y |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  | 1 > 0 |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  | 1 < 0 |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  | X1 |

---

## Page 39

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Reciprocal transformation, Y = β + β1/X1 + β2/X2 + ε, Asymptote, β1 > 0, β1 < 0 | **Exam Signal:** No
> **Summary:** This slide illustrates the Reciprocal Transformation, providing the regression equation and a graph that includes an asymptote, demonstrating the behavior for both positive and negative β1.

Reciprocal Transformation

Y

X1
β1 > 0

β1 < 0

X
X
Y
ε
β
β
β
+
+
+
=



Asymptote

### Table 1

| Reciprocal Transformation |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |
| Y | = |  | + |  |  | + |  |  | + |  |
| i |  |  |  |  |  |  |  |  |  | i |
|  |  |  |  |  | X |  |  | X |  |  |
|  |  |  |  |  | 1
i |  |  | 2
i |  |  |
| Y |  |  |  |  |  |  |  |  |  |  |
|  | Asymptote |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  | 1 < 0 |  |  |  |
|  |  |  |  |  |  |  | 1 > 0 |  |  |  |
|  |  |  |  |  |  |  |  |  |  | X1 |

### Table 2

| β2 |  |
| --- | --- |
| X. |  |
| 1i | 2i |

---

## Page 40

> **Title:** Non-Linear Transformations | **Type:** diagram_explanation | **Concepts:** Exponential transformation, Y = e^(β + β1X1 + β2X2) + ε, β1 > 0, β1 < 0 | **Exam Signal:** No
> **Summary:** This slide details the Exponential Transformation, showing the regression equation with an exponential function and a graph illustrating the trends for positive and negative β1.

Exponential Transformation

Y

X1

β1 > 0

β1 < 0

i
X
X
i

i
i
e
Y
ε
β
β
β
+
+
=

### Table 1

| Exponential Transformation |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | + |  | X |  |  | + |  | X |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Y | = | e |  |  |  |  |  | i |  |  |  |  | i |  |
| i |  |  |  |  |  |  |  |  |  |  |  |  |  | i |
| Y |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 > 0 |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  | 1 < 0 |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  | X1 |

---

## Page 41

> **Title:** Examples | **Type:** table | **Concepts:** Non-linear transformations, Standard linear regression, Exponential model, Quadratic model, Reciprocal model, Logarithmic model, Power model, Transform, Regression equation, Predicted value | **Exam Signal:** No
> **Summary:** This slide provides a table summarizing various non-linear transformation methods, including their transformation, regression equation, and predicted value formulas.

Examp: Non-Linear Transformations

### Table 1

| Method | Transform | Regression equation | Predicted value (y) |
| --- | --- | --- | --- |
| Standard linear regression | None | y = bo + bx | y = bo + bx |
| Exponential |  |  |  |
| model | DV = log(y) | log(y) = b0 + b1x | y = 10bo + b1x |
| Quadratic |  |  |  |
| DV = sqrt(y) | sqrt(y) = bo + b1x | y = ( bo + b1x ){2 |  |
| model |  |  |  |
| Reciprocal |  |  |  |
| DV = 1/y | 1/y = b0 + b1x | y = 1 / ( bo + bx ) |  |
| model |  |  |  |
| Logarithmic |  |  |  |
| IV = log(x) | y= bo + blog(x) | y = bo + blog(x) |  |
| model |  |  |  |
| Power model | DV = log(y) | log(y)= | y = 10bo + blog(x) |
| IV = log(x) | bo + blog(x) |  |  |

---

## Page 42

> **Title:** Introduction to Regression Analysis | **Type:** other | **Concepts:** Error term | **Exam Signal:** No
> **Summary:** This slide is a title slide for the topic "The Error term".

The Error term

---

## Page 43

> **Title:** Introduction to Regression Analysis | **Type:** comparison | **Concepts:** Errors vs residuals, Error (disturbance), Deviation from true value, Residual, Difference from estimated value, Prediction error | **Exam Signal:** No
> **Summary:** This slide clarifies the distinction between errors (deviation from the true value) and residuals (difference from the estimated value), also known as prediction error.

Errors Vs residuals

• Two closely related and easily confused measures
• The error (or disturbance) of an observation is the deviation of the observed value from the true value of a quantity of interest (for example, a population mean)
• The residual is the difference between the observed value and the estimated value of the quantity of interest (for example, a sample mean). Also called, prediction error

---

## Page 44

> **Title:** Introduction to Regression Analysis | **Type:** numerical_example | **Concepts:** Residual analysis, Residual, Observed value, Predicted value, e = y - ŷ | **Exam Signal:** No
> **Summary:** This slide defines residual analysis by providing the formula "Residual = Observed value - Predicted value" and includes a table with example values for observed (y), predicted (ŷ), and residual (e).

Residual Analysis

Residual = Observed value - Predicted value
e = y - ŷ
x
y
ŷ
e
65.411
4.589
71.849
-6.849
78.288
-8.288
81.507
13.493
87.945
-2.945

### Extracted from Image (OCR)

+
-5
1m
-10
Independent variable, X
"

---

## Page 45

> **Title:** Non-Linear Transformations | **Type:** concept | **Concepts:** Effect of Non-Linear Transformations, Residual plots, Correlation coefficients, Coefficient of determination (R2), Raw-score R2, Transformed R2 | **Exam Signal:** No
> **Summary:** This slide explains how to test the effect of a non-linear transformation by analyzing residual plots and correlation coefficients, and comparing the coefficient of determination (R2) before and after transformation.

Effect of Non-Linear Transformations

• Testing the effect of a transformation method involves looking at residual plots and correlation coefficients
Did the Transformation Work?

• Compute the coefficient of determination (R2).
• Choose a transformation method.
• Transform the independent variable, dependent variable, or both.
• Conduct a regression analysis, using the transformed variables.
• Compute the coefficient of determination (R2), based on the transformed variables.
• If the transformed R2 is greater than the raw-score R2, the transformation was successful.
• If not, try a different transformation method.
---

---

## Page 46

> **Title:** Examples | **Type:** example | **Concepts:** Non-Linear Transformations example, y' = (b0 + b1x)^2, R^2=0.96, R^2=0.88, Predicted value of y, Independent variable, Y-intercept, Slope | **Exam Signal:** No
> **Summary:** This slide presents an example of non-linear transformations, showing how a dependent variable can be transformed and the resulting R-squared values for different models.

Example: Non-Linear Transformations

• x
• y

y't = b0 + b1x

x
yt
1.41
1.00
2.45
3.74
3.87
5.48
6.32
8.60
8.66

y' = ( b0 + b1x )^2

y' = predicted value of y in its original units
x = independent variable
b0 = y-intercept of transformation regression line
b1 = slope of transformation regression line
R^2=0.96 
R^2=0.88

### Extracted from Image (OCR)

0.5
•
-0.5
i0
-1
5o
-5
-10
-15

---

## Page 47

> **Title:** Coefficient of Determination (R^2) | **Type:** concept | **Concepts:** Coefficient of Determination, R2, Null hypothesis rejection, Relationship between Y and X variables, Strength measured by R2 | **Exam Signal:** No
> **Summary:** This slide introduces the Coefficient of Determination (R2) as a measure of the strength of the relationship between Y and X variables when the null hypothesis is rejected.

Coefficient of Determination

When null hypothesis is rejected, a relationship between Y and the X variables exists.
Strength measured by R2

### Table 1

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

### Table 2

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

### Table 3

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

### Table 4

|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

---

## Page 48

> **Title:** Coefficient of Determination (R^2) | **Type:** definition | **Concepts:** Coefficient of determination (R^2), Proportion of variance in dependent variable, Predictable from independent variable, Ranges from 0 to 1, Square of correlation, R^2 of 0, R^2 of 1 | **Exam Signal:** No
> **Summary:** This slide defines the coefficient of determination (R2) as the proportion of variance in the dependent variable explained by the independent variable, noting its range from 0 to 1 and its interpretation.

Coefficient of Determination (R^2)

The coefficient of determination (denoted by R^2) is a key output of regression analysis. It is interpreted as the proportion of the variance in the dependent variable that is predictable from the independent variable

• It ranges from 0 to 1.
• With linear regression, the coefficient of determination is also equal to the square of the correlation between x and y scores.
• An R^2 of 0 means that the dependent variable cannot be predicted from the independent variable.
• An R^2 of 1 means the dependent variable can be predicted without error from the independent variable.

---

## Page 49

> **Title:** Coefficient of Determination (R^2) | **Type:** concept | **Concepts:** Measures of Variation in Prediction, Explained variation, Sum of squares due to regression, Unexplained variation, Error sum of squares, Total sum of squares | **Exam Signal:** No
> **Summary:** This slide lists the key measures of variation in prediction, including explained variation (sum of squares due to regression), unexplained variation (error sum of squares), and total sum of squares.

Measures of Variation in

Prediction

• Explained variation (sum of squares due to regression)

• Unexplained variation (error sum of squares)

• Total sum of squares

---

## Page 50

> **Title:** Coefficient of Determination (R^2) | **Type:** definition | **Concepts:** Measures of Variation in Prediction, Total variation in target variable (SST), Prediction error (Residual Sum of Squares, RSS/SSE), Variation not explained by model, Total variation in prediction (SSR) | **Exam Signal:** No
> **Summary:** This slide defines and explains the measures of variation in prediction, including Total Variation (SST), Prediction Error (RSS/SSE) representing unexplained variation, and Total Variation in Prediction (SSR).

Measures of Variation in Prediction

(
)
iy
y
−

1) Total variation in target variable (or Total Variance in y)=

2) The prediction error (Residual) captures the difference of the true values from the fitted line. 
So, RSS as a whole gives us the variation in the target variable that is not explained by our

model.  RSS/SSE=

Lets target variable y

= SST

3) Total variation in prediction (or Total Variance) SSR=

ˆ
(
)
i
i
y
y
−


ˆ
(
)
iy
y
−


---

## Page 51

> **Title:** Coefficient of Determination (R^2) | **Type:** concept | **Concepts:** SST, SSR, SSE, Total Sum of Squares, Sum of Squares due to Regression, Residual Sum of Square | **Exam Signal:** No
> **Summary:** This slide defines the measures of variations in prediction, including Total Sum of Squares (SST), Sum of Squares due to Regression (SSR), and Sum of Squares due to Error (SSE), illustrating their relationship with the formula SST = SSR + SSE.

Measure of Variations in Prediction

where:

     SST = total sum of squares/ total variation in target variable
     SSR = sum of squares due to regression
     SSE = sum of squares due to error also called Residual sum of square (RSS)

SST = SSR + SSE

### Table 1

| Measure of Variations in Prediction |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  | SST    =    SSR    +    SSE |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | ( | y− | ) |  | ˆ( | y− | ) |  |  | ( | y | y− | ) |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | iy |  | = |  | iy |  |  | + |  |  | i | i |  |
| where: |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | SST = total sum of squares/ total variation in target variable |  |  |  |  |  |  |  |  |  |  |  |  |
|  | SSR = sum of squares due to regression |  |  |  |  |  |  |  |  |  |  |  |  |
|  | SSE = sum of squares due to error also called Residual sum of square (RSS) |  |  |  |  |  |  |  |  |  |  |  |  |

---

## Page 52

> **Title:** Coefficient of Determination (R^2) | **Type:** definition | **Concepts:** Coefficient of Determination, R-squared, Explained variation, Unexplained variation, SST, SSR, SSE | **Exam Signal:** No
> **Summary:** This slide defines the Coefficient of Determination (R-squared) as a numerical index reflecting how much variation in a response variable is accounted for by predictor variables, providing its formula as SSR/SST or (SST-SSE)/SST.

Coefficient of Determination R2

R2 = SSR/SST

A numerical index that reflects the degree to which variation in a response or outcome variable 
(e.g., workers’ incomes) is accounted for by its relationship with two or more predictor variables 
(e.g., age, gender, years of education)

OR
It is the proportion of the variation in the dependent variable that is predictable from the independent 
variable(s).

R-squared = (SST-SSE)/SST

= Explained variation/ Total variation

= 1 – Unexplained variation/ Total variation

So R-squared gives the degree of variability in the target variable that is explained by the model or the independent 
variables. If this value is 0.7, then it means that the independent variables explain 70% of the variation in the target variable.

---

## Page 53

> **Title:** Coefficient of Determination (R^2) | **Type:** concept | **Concepts:** R-squared limitations, Redundant variables, Adjusted R-squared | **Exam Signal:** No
> **Summary:** This slide discusses the problems with R-squared, specifically that its value never decreases when adding variables to a regression model, even redundant ones, leading to the introduction of Adjusted R-squared to address this issue.

Problems with R2   (score)

• Its value never decreases no matter the number of variables we add 
to our regression model. 
• That is, even if we are adding redundant variables to the data, the 
value of R-squared does not decrease. 
• It either remains the same or increases with the addition of new 
independent variables.

• Why? (Hint: See, how its defined, SSR remains same and SST?)
• This clearly does not make sense because some of the independent 
variables might not be useful in determining the target variable. 
• Adjusted R-squared deals with this issue.

---

## Page 54

> **Title:** Coefficient of Determination (R^2) | **Type:** definition | **Concepts:** Adjusted R-squared, Multiple regression, Model complexity, n-number of observations, k-number of parameters | **Exam Signal:** No
> **Summary:** This slide defines the Adjusted R-squared statistic, which accounts for the automatic increase of R-squared when extra explanatory variables are added to a model and provides its mathematical formula.

Adjusted R-squared Statistic

• It is an attempt to account for the phenomenon of the R^2 automatically 
increasing when extra explanatory variables are added to the model.
• This statistic is used in a multiple regression analysis, because it does not 
automatically rise when an extra explanatory variable is added. 
• In generally rises when the t-statistic of an extra variable exceeds unity (1), 
so does not necessarily imply the extra variable is significant.
• It is usually written as (R-bar squared):
R
)
1(
R
k
n

k
R
R
−
−

−
−
=

n-number of observations in the data, k-number of parameters/variables/predictors

---

## Page 55

> **Title:** Coefficient of Determination (R^2) | **Type:** definition | **Concepts:** Fraction of Variance Unexplained, FVU, Regressand, Explained variance, R-squared | **Exam Signal:** No
> **Summary:** This slide defines the Fraction of Variance Unexplained (FVU) as the proportion of variance in the dependent variable that cannot be explained by the explanatory variables, relating it to R-squared with the formula FVU = 1 - R^2.

Fraction of variance unexplained (FVU)

•  In the context of a regression task, FUV is the fraction of variance of 
the regressand (dependent variable) Y which cannot be explained, 
i.e., which is not correctly predicted, by the explanatory variables X.
• Linear regression y=mx+c+e, where e is the error (residual or 
unexplained error) . If e is zero for all predictions, FVU is zero
•                               FUV=1-R^2

R2 = SSR/SST

FVU =1- SSR/SST

### Table 1

| Fraction of variance unexplained (FVU) |
| --- |
| •  In the context of a regression task, FUV is the fraction of variance of |
| the regressand (dependent variable) Y which cannot be explained, |
| i.e., which is not correctly predicted, by the explanatory variables X. |
| • Linear regression y=mx+c+e, where e is the error (residual or |
| unexplained error) . If e is zero for all predictions, FVU is zero |
| •                               FUV=1-R^2 |
| R2 = SSR/SST |
| FVU =1- SSR/SST |

---

## Page 56

> **Title:** Bias-Variance Trade-Off | **Type:** concept | **Concepts:** Bias-Variance, Supervised machine learning, Prediction error, Bias, Variance, Irreducible error | **Exam Signal:** No
> **Summary:** This slide introduces the concepts of Bias and Variance in supervised machine learning, explaining that the aim is to estimate the mapping function with prediction error broken down into Bias, Variance, and Irreducible error.

Bias-Variance

• In supervised machine learning an algorithm learns a model from training data.
• Aim is to best estimate the mapping function (f) for the output variable (Y) given the input data (X).
• But, practically it's not possible to achieve exact estimation, resulting in the prediction error
• Prediction Error = |Y - f|
• Three Types of Prediction error (PE): Bias, Variance, Irreducible error
• Is PE a Random Variable?? HOW ??
---

---

## Page 57

> **Title:** Bias-Variance Trade-Off | **Type:** diagram_explanation | **Concepts:** Prediction error decomposition, Model change, Training data | **Exam Signal:** No
> **Summary:** This slide briefly highlights the concept of prediction error decomposition by considering how the model changes with respect to training data and its own estimations.

Prediction error decomposition

wrt to some training data Y, how's the model changing

wrt to some estimation by the model, how's the model changing

### Table 1

| Prediction error decomposition |
| --- |
| wrt to some estimation by the model, howz the model changing |
| wrt to some training data Y, howz the model changing |

---

## Page 58

> **Title:** Bias-Variance Trade-Off | **Type:** definition | **Concepts:** Bias Error, Simplifying assumptions, Accuracy, Low Bias, High Bias, Linear algorithms, Decision Trees, k-Nearest Neighbors, Support Vector Machines, Linear Regression, Linear Discriminant Analysis, Logistic Regression | **Exam Signal:** No
> **Summary:** This slide defines Bias error as simplifying assumptions made by a model, describing high-bias models as less flexible but faster to learn, and providing examples of both low-bias and high-bias machine learning algorithms.

Bias Error

Three Types of Prediction error: Bias, Variance, Irreducible error ??
• Bias are the simplifying assumptions made by a model to make the target 
function easier to learn.
• Generally, linear algorithms have a high bias making them fast to learn and 
easier to understand but generally less flexible.
• Lower predictive performance on complex problems
• Measures accuracy or quality of the estimator

• Low Bias: Suggests less assumptions about the form of the target function.

• High-Bias: Suggests more assumptions about the form of the target function.

• Examples of low-bias machine learning algorithms include: Decision Trees, k-Nearest Neighbors and 
Support Vector Machines.

• Examples of high-bias machine learning algorithms include: Linear Regression, Linear Discriminant 
Analysis and Logistic Regression.

---

## Page 59

> **Title:** Bias-Variance Trade-Off | **Type:** definition | **Concepts:** Variance error, Target function estimate, Training data changes, Precision, Low Variance, High Variance | **Exam Signal:** No
> **Summary:** This slide defines Variance error as the amount an estimate of the target function changes with different training data, emphasizing that low variance indicates stability and precision in the estimator despite dataset changes.

Variance error

• Variance is the amount that the estimate of the target function will 
change if different training data was used.
• The target function is estimated from the training data by a 
estimation algorithm.
• It is expected the algorithm to have some variance.
• The estimation should not change much with change in the dataset
• This implies that the algorithm is good at picking out the hidden 
underlying mapping between the inputs and the output variables
• Measures precision or specificity of the estimator

• Low Variance: Suggests small changes to the estimate of the target function with changes to the 
training dataset.

• High Variance: Suggests large changes to the estimate of the target function with changes to the 
training dataset.

---

## Page 60

> **Title:** Bias-Variance Trade-Off | **Type:** concept | **Concepts:** High variance algorithms, Nonlinear machine learning algorithms, Low variance algorithms, Linear Regression, Linear Discriminant Analysis, Logistic Regression, Decision Trees, k-Nearest Neighbors, Support Vector Machines | **Exam Signal:** No
> **Summary:** This slide categorizes machine learning algorithms based on their variance, noting that nonlinear algorithms often have high variance while linear algorithms tend to have low variance, and provides examples for each category.

Variance error

• Generally, nonlinear machine learning algorithms that have a lot of flexibility have a high variance.

• Examples of low-variance machine learning algorithms include: Linear Regression, Linear Discriminant Analysis and Logistic Regression.

• Examples of high-variance machine learning algorithms include: Decision Trees, k-Nearest Neighbors and Support Vector Machines.
---

---

## Page 61

> **Title:** Bias-Variance Trade-Off | **Type:** concept | **Concepts:** Bias-Variance Trade-Off, Low bias, Low variance, Linear machine learning algorithms, Nonlinear machine learning algorithms, k-nearest neighbors, Support Vector Machines, Model complexity | **Exam Signal:** No
> **Summary:** This slide explains the Bias-Variance Trade-Off, highlighting the challenge of achieving both low bias and low variance and demonstrating how to adjust this trade-off in algorithms like k-nearest neighbors and Support Vector Machines.

Bias-Variance Trade-Off

• For any ML algorithm, AIM is to achieve low bias and low variance.
However, a general trend is
• Linear machine learning algorithms often have a high bias but a low 
variance.
• Nonlinear machine learning algorithms often have a low bias but a 
high variance.
                         HOW TO KEEP A BALANCE?   
                              A Major ML Challenge !!

The k-nearest neighbors algorithm has low bias and high variance, but the trade-off can be changed by increasing the value 
of k which increases the number of neighbors that contribute to the prediction and in turn increases the bias of the model.

The support vector machine algorithm has low bias and high variance, but the trade-off can be changed by increasing the C 
parameter that influences the number of violations of the margin allowed in the training data which increases the bias but 
decreases the variance.

---

## Page 62

> **Title:** Bias-Variance Trade-Off | **Type:** diagram_explanation | **Concepts:** High variance, High bias, Overfitting, Underfitting, Good balance | **Exam Signal:** No
> **Summary:** This slide uses a table to visually present examples of high variance (overfitting), high bias (underfitting), and a good balance in model performance.

Examples

### Table 1

| High variance | High bias | Low bias, low variance |
| --- | --- | --- |
| y | y | y |
| overfitting | underfitting | Good balance |

---

## Page 63

> **Title:** Bias-Variance Trade-Off | **Type:** diagram_explanation | **Concepts:** Bias-variance Trade-off, Model Selection, High Bias, Low Bias, Low Variance, High Variance, Test Sample, Training Sample, Overfit region, Underfit region, Model Complexity | **Exam Signal:** No
> **Summary:** This slide presents a diagram illustrating the Bias-Variance Trade-off in relation to model complexity, showing how models can fall into underfit or overfit regions depending on their bias and variance characteristics.

Bias-variance Trade-off/Model Selection

### Table 1

| High Bias | Low Bias |
| --- | --- |
| Low Variance | High Variahce |
| Test Sample |  |
| overfit region |  |
| underfit region | Training Sample |
| Low | High |
| Model Complexity |  |
| 10/3/19 |  |
