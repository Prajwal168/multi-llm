# Python

## Introduction

Python is a high-level, interpreted, general-purpose programming language known for its simplicity, readability, and versatility. Created with the philosophy that code should be easy to read and write, Python has become one of the most popular programming languages in the world. It supports multiple programming paradigms, including procedural programming, object-oriented programming, and functional programming, making it suitable for beginners as well as experienced developers.

Python is widely used in web development, data science, artificial intelligence, machine learning, automation, cybersecurity, scientific computing, cloud computing, and software development. Its extensive standard library and rich ecosystem of third-party packages enable developers to build applications efficiently without reinventing common functionality.

Unlike compiled languages such as C or C++, Python is interpreted, meaning the source code is executed line by line by the Python interpreter. This feature simplifies development, testing, and debugging while allowing programs to run across multiple operating systems with minimal modifications.

---

## History of Python

Python was created by **Guido van Rossum** at Centrum Wiskunde & Informatica (CWI) in the Netherlands. Development began in the late 1980s, and the first public release, Python 0.9.0, was made available in February 1991.

The language was designed to overcome limitations in existing programming languages while emphasizing readability and programmer productivity. Guido named the language "Python" after the British comedy television series *Monty Python's Flying Circus*, rather than the snake.

Some major milestones include:

* **1991:** Python 0.9.0 released
* **1994:** Python 1.0 introduced functional programming features
* **2000:** Python 2.0 added garbage collection and Unicode support
* **2008:** Python 3.0 introduced major improvements and removed outdated features
* **2020:** Official support for Python 2 ended
* **Present:** Python 3 continues to evolve with performance improvements, typing enhancements, and new language features.

Today, Python is maintained by the Python Software Foundation (PSF), with contributions from developers around the world.

---

## Features of Python

Python possesses numerous features that contribute to its popularity.

### Simple and Readable

Python uses a clean syntax that resembles natural English. Programs require fewer lines of code compared to many other programming languages.

### Interpreted Language

Python executes programs through an interpreter, eliminating the need for a separate compilation process during development.

### Platform Independent

Python programs can run on Windows, Linux, macOS, and several other operating systems with little or no modification.

### Object-Oriented

Python supports classes, objects, inheritance, encapsulation, abstraction, and polymorphism.

### Dynamically Typed

Variable types are determined during execution rather than at compile time.

### Extensive Standard Library

Python includes built-in modules for:

* Mathematics
* File handling
* Networking
* Operating system interaction
* JSON processing
* Regular expressions
* Date and time
* Threading
* Database connectivity

### Open Source

Python is free to use and maintained by a large global community.

### Large Ecosystem

Thousands of external libraries are available through the Python Package Index (PyPI).

Examples include:

* NumPy
* Pandas
* TensorFlow
* Flask
* Django
* FastAPI
* Scikit-learn
* OpenCV

---

## Applications of Python

Python is used across numerous domains.

### Web Development

Popular frameworks include:

* Django
* Flask
* FastAPI

### Artificial Intelligence

Python is the dominant language for AI due to libraries such as:

* TensorFlow
* PyTorch
* Hugging Face Transformers

### Machine Learning

Machine learning workflows commonly use:

* NumPy
* Pandas
* Scikit-learn
* XGBoost

### Data Analysis

Python enables efficient processing and visualization of large datasets using:

* Pandas
* Matplotlib
* Plotly

### Automation

Python scripts automate repetitive tasks such as:

* File management
* Email processing
* Data extraction
* System administration

### Cybersecurity

Python is frequently used for:

* Network scanning
* Log analysis
* Ethical hacking tools
* Security automation

### Cloud Computing

Python integrates with major cloud providers including AWS, Microsoft Azure, and Google Cloud Platform.

### Desktop Applications

Frameworks include:

* Tkinter
* PyQt
* Kivy

### Internet of Things (IoT)

Python is widely used with Raspberry Pi and embedded systems for sensor control and automation.

---

## Installing Python

Python can be downloaded from the official Python website.

### Windows

1. Download the latest installer.
2. Run the installer.
3. Select **Add Python to PATH**.
4. Complete installation.
5. Verify installation.

```bash
python --version
```

or

```bash
py --version
```

### Linux

Many Linux distributions include Python by default.

```bash
python3 --version
```

If not installed:

```bash
sudo apt install python3
```

### macOS

Using Homebrew:

```bash
brew install python
```

Verify installation:

```bash
python3 --version
```

---

## Running Python Programs

### Interactive Mode

Open the interpreter:

```bash
python
```

Example:

```python
>>> print("Hello World")
Hello World
```

### Script Mode

Create a file:

```text
hello.py
```

Code:

```python
print("Hello World")
```

Execute:

```bash
python hello.py
```

---

## Python Syntax

Python syntax emphasizes readability.

Example:

```python
name = "Alice"
age = 20

if age >= 18:
    print("Adult")
else:
    print("Minor")
```

Notice that Python uses **indentation** instead of braces to define code blocks.

---

## Comments

Comments improve code readability.

Single-line comment:

```python
# This is a comment
```

Multi-line comment:

```python
"""
This is
a multiline
comment.
"""
```

---

## Variables

Variables store data in memory.

Example:

```python
name = "John"
age = 25
height = 5.8
```

Variables are created automatically upon assignment.

Python follows dynamic typing.

```python
x = 10
x = "Python"
```

The same variable can reference different data types during execution.

### Variable Naming Rules

Valid examples:

```python
student_name
totalMarks
price1
```

Invalid examples:

```python
1name
student-name
class
```

---

## Constants

Python does not provide true constants.

Developers use uppercase naming convention.

```python
PI = 3.14159
MAX_USERS = 100
```

These values should not be modified after declaration.

---

## Data Types

Python provides several built-in data types.

### Integer

```python
age = 20
```

### Float

```python
salary = 35000.75
```

### Complex

```python
z = 3 + 4j
```

### Boolean

```python
is_valid = True
```

### String

```python
language = "Python"
```

### List

```python
numbers = [1,2,3]
```

### Tuple

```python
point = (10,20)
```

### Set

```python
fruits = {"Apple","Banana"}
```

### Dictionary

```python
student = {
    "name":"Alice",
    "age":21
}
```

---

## Type Conversion

Python supports automatic and explicit conversion.

```python
x = int("100")

y = float(5)

z = str(25)
```

Example:

```python
print(int(5.7))

print(float(10))

print(str(123))
```

---

## Type Checking

Use the `type()` function.

```python
age = 25

print(type(age))
```

Output:

```python
<class 'int'>
```

---

## Operators

Python provides several categories of operators.

### Arithmetic Operators

```python
a = 10
b = 3

print(a+b)
print(a-b)
print(a*b)
print(a/b)
print(a//b)
print(a%b)
print(a**b)
```

### Comparison Operators

```python
print(5 > 2)

print(5 == 5)

print(3 != 7)
```

### Logical Operators

```python
x = True
y = False

print(x and y)

print(x or y)

print(not x)
```

### Assignment Operators

```python
x = 5

x += 2

x *= 3
```

### Membership Operators

```python
numbers = [1,2,3]

print(2 in numbers)

print(10 not in numbers)
```

### Identity Operators

```python
a = [1,2]
b = a
c = [1,2]

print(a is b)

print(a is c)
```

---

## Input and Output

Input is obtained using the `input()` function.

```python
name = input("Enter your name: ")

print(name)
```

Numeric input:

```python
age = int(input("Age: "))
```

Formatted output:

```python
name = "Alice"
marks = 95

print(f"{name} scored {marks}")
```

String formatting improves readability and is preferred over manual concatenation.

---

## Strings

Strings are immutable sequences of Unicode characters.

Creating strings:

```python
name = "Python"

language = 'Programming'

text = """Multiple
line
string"""
```

Useful operations:

```python
text = "Python"

print(len(text))

print(text.upper())

print(text.lower())

print(text.replace("Py","My"))

print(text[0])

print(text[-1])
```

Common string methods include:

* upper()
* lower()
* strip()
* replace()
* split()
* join()
* find()
* startswith()
* endswith()

Strings support indexing and slicing.

```python
text = "Programming"

print(text[0:6])

print(text[3:])

print(text[::-1])
```

---

## Escape Characters

Python supports escape sequences.

```python
print("Hello\nWorld")

print("Python\tProgramming")

print("She said \"Hello\"")
```

These characters help format output and include special symbols inside strings.

---

## Summary

Python is a powerful, readable, and versatile programming language that supports a wide variety of applications. Its simple syntax, dynamic typing, extensive libraries, and cross-platform compatibility make it an excellent choice for beginners and professionals alike. Understanding its history, features, syntax, variables, data types, operators, and string manipulation forms the foundation for learning advanced topics such as functions, object-oriented programming, file handling, exception handling, and modern software development.
## Conditional Statements

Conditional statements allow a program to make decisions based on whether a condition evaluates to `True` or `False`. They are fundamental to controlling the flow of execution and enable programs to react differently under different circumstances.

### The `if` Statement

The simplest conditional statement is the `if` statement.

```python
age = 20

if age >= 18:
    print("Eligible to vote")
```

If the condition evaluates to `True`, the indented block is executed.

### The `if-else` Statement

The `else` block executes when the condition is false.

```python
age = 15

if age >= 18:
    print("Adult")
else:
    print("Minor")
```

### The `if-elif-else` Statement

When multiple conditions need to be checked, use `elif`.

```python
marks = 82

if marks >= 90:
    grade = "A+"
elif marks >= 80:
    grade = "A"
elif marks >= 70:
    grade = "B"
elif marks >= 60:
    grade = "C"
else:
    grade = "Fail"

print(grade)
```

Python evaluates conditions sequentially. Once a condition is true, the remaining conditions are skipped.

### Nested Conditions

Conditional statements can be nested inside other conditional statements.

```python
age = 25
citizen = True

if age >= 18:
    if citizen:
        print("Eligible to vote")
    else:
        print("Citizenship required")
```

### Ternary Operator

Python supports concise conditional expressions.

```python
age = 20

status = "Adult" if age >= 18 else "Minor"

print(status)
```

---

## Loops

Loops execute a block of code repeatedly until a condition becomes false or the iterable is exhausted.

Python provides two primary loops:

- `for`
- `while`

### For Loop

The `for` loop iterates over sequences.

```python
for i in range(5):
    print(i)
```

Output:

```
0
1
2
3
4
```

### Looping Through a List

```python
languages = ["Python", "Java", "C++"]

for language in languages:
    print(language)
```

### The `range()` Function

`range()` generates a sequence of numbers.

```python
for i in range(1, 6):
    print(i)
```

Using a step value:

```python
for i in range(0, 10, 2):
    print(i)
```

Output:

```
0
2
4
6
8
```

### While Loop

A `while` loop executes as long as the condition remains true.

```python
count = 1

while count <= 5:
    print(count)
    count += 1
```

### Infinite Loop

```python
while True:
    print("Running...")
```

Infinite loops should always include a condition to terminate using `break`.

### Break Statement

`break` exits the nearest loop immediately.

```python
for i in range(10):
    if i == 5:
        break
    print(i)
```

### Continue Statement

`continue` skips the current iteration.

```python
for i in range(6):
    if i == 3:
        continue
    print(i)
```

### Pass Statement

`pass` acts as a placeholder.

```python
for i in range(5):
    pass
```

---

## Functions

Functions group reusable code into logical units.

Advantages include:

- Code reuse
- Better organization
- Easier debugging
- Improved readability
- Modular programming

### Defining a Function

```python
def greet():
    print("Hello")
```

Calling the function:

```python
greet()
```

### Function with Parameters

```python
def greet(name):
    print("Hello", name)

greet("Alice")
```

### Returning Values

```python
def square(number):
    return number * number

result = square(5)

print(result)
```

### Default Parameters

```python
def greet(name="Guest"):
    print("Welcome", name)

greet()

greet("John")
```

### Keyword Arguments

```python
def student(name, age):
    print(name, age)

student(age=20, name="Alice")
```

### Variable-Length Arguments

```python
def total(*numbers):
    print(sum(numbers))

total(10, 20, 30)
```

Keyword variable arguments:

```python
def student(**details):
    print(details)

student(name="Alice", age=21)
```

### Scope of Variables

Local variable:

```python
def test():
    x = 10
    print(x)
```

Global variable:

```python
x = 100

def display():
    print(x)
```

Using the `global` keyword:

```python
count = 0

def increment():
    global count
    count += 1
```

---

## Lambda Functions

Lambda functions are anonymous functions written in a single line.

General syntax:

```python
lambda arguments: expression
```

Example:

```python
square = lambda x: x * x

print(square(6))
```

Multiple arguments:

```python
add = lambda a, b: a + b

print(add(10, 20))
```

Sorting using lambda:

```python
students = [
    ("Alice", 82),
    ("Bob", 95),
    ("Charlie", 78)
]

students.sort(key=lambda x: x[1])

print(students)
```

Lambda functions are commonly used with:

- map()
- filter()
- sorted()
- reduce()

---

## Recursion

Recursion occurs when a function calls itself to solve a smaller instance of the same problem.

Every recursive function requires:

- Base case
- Recursive case

### Factorial Example

```python
def factorial(n):
    if n == 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))
```

### Fibonacci Series

```python
def fibonacci(n):
    if n <= 1:
        return n

    return fibonacci(n - 1) + fibonacci(n - 2)

print(fibonacci(6))
```

Advantages of recursion include elegant solutions for tree traversal, divide-and-conquer algorithms, and mathematical computations.

However, excessive recursion may lead to stack overflow, so iterative solutions are often preferred for deep recursion.

---

## Modules

A module is a Python file containing functions, classes, and variables.

Example:

**math_operations.py**

```python
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
```

Using the module:

```python
import math_operations

print(math_operations.add(5, 4))
```

Importing individual functions:

```python
from math_operations import add

print(add(10, 5))
```

Importing all members:

```python
from math_operations import *
```

Common built-in modules include:

- math
- random
- os
- sys
- datetime
- json
- pathlib
- statistics
- collections

---

## Packages

A package is a directory containing multiple related modules.

Example:

```
calculator/
│
├── __init__.py
├── arithmetic.py
└── scientific.py
```

Using a package:

```python
from calculator.arithmetic import add

print(add(10, 20))
```

Packages help organize large applications into logical components, improve maintainability, and encourage code reuse.

---

## Summary

Conditional statements, loops, functions, recursion, modules, and packages form the core building blocks of Python programming. They enable developers to control program flow, organize reusable code, solve complex problems recursively, and structure applications into modular, maintainable components. Mastering these concepts provides the foundation for advanced topics such as object-oriented programming, file handling, exception handling, and software architecture.
---

# File Handling

File handling is the process of creating, reading, writing, updating, and deleting files stored on a computer. Python provides built-in functions and methods that make file operations simple and efficient. File handling is essential for storing application data, reading configuration files, processing logs, and managing datasets.

## Opening a File

The `open()` function is used to open a file.

Syntax:

```python
open(filename, mode)
```

Example:

```python
file = open("example.txt", "r")
```

The first parameter specifies the file name, while the second parameter specifies the mode in which the file is opened.

## File Modes

| Mode | Description |
|------|-------------|
| `r` | Read (default mode) |
| `w` | Write (creates or overwrites a file) |
| `a` | Append to an existing file |
| `x` | Create a new file; raises an error if it already exists |
| `rb` | Read binary files |
| `wb` | Write binary files |

---

## Reading a File

### Read Entire File

```python
file = open("example.txt", "r")

content = file.read()

print(content)

file.close()
```

### Read One Line

```python
file = open("example.txt", "r")

print(file.readline())

file.close()
```

### Read All Lines

```python
file = open("example.txt", "r")

lines = file.readlines()

print(lines)

file.close()
```

---

## Writing to a File

```python
file = open("example.txt", "w")

file.write("Hello Python")

file.close()
```

If the file already exists, its contents will be overwritten.

---

## Appending to a File

```python
file = open("example.txt", "a")

file.write("\nNew Line")

file.close()
```

Appending preserves the existing content and adds new data at the end.

---

## Using the `with` Statement

The recommended way to handle files is by using the `with` statement. It automatically closes the file after the operations are completed.

```python
with open("example.txt", "r") as file:
    data = file.read()

print(data)
```

Advantages include:

- Automatic file closing
- Cleaner code
- Better resource management
- Reduced chance of file corruption

---

## Exception Handling

Errors may occur while a program is running. Exception handling allows the program to continue gracefully instead of terminating unexpectedly.

Common runtime errors include:

- Division by zero
- Invalid user input
- File not found
- Index out of range
- Type mismatch

---

## The `try-except` Block

```python
try:
    number = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero.")
```

If an exception occurs, Python executes the corresponding `except` block.

---

## Multiple Exceptions

```python
try:
    number = int(input("Enter number: "))
    result = 100 / number

except ValueError:
    print("Invalid input.")

except ZeroDivisionError:
    print("Division by zero is not allowed.")
```

---

## Using `else`

The `else` block executes only if no exception occurs.

```python
try:
    value = int(input())

except ValueError:
    print("Invalid")

else:
    print("Successful")
```

---

## Using `finally`

The `finally` block always executes.

```python
try:
    file = open("data.txt")

except FileNotFoundError:
    print("File not found")

finally:
    print("Execution completed")
```

The `finally` block is commonly used for cleaning up resources.

---

# Object-Oriented Programming (OOP)

Object-Oriented Programming is a programming paradigm that organizes software around objects rather than functions. Objects combine data and behavior into a single unit.

Python fully supports object-oriented programming.

The four fundamental principles are:

- Encapsulation
- Abstraction
- Inheritance
- Polymorphism

---

## Classes and Objects

A class acts as a blueprint.

```python
class Student:
    pass
```

Creating an object:

```python
student = Student()
```

---

## Constructor

The constructor initializes object attributes.

```python
class Student:

    def __init__(self, name, age):
        self.name = name
        self.age = age
```

Creating objects:

```python
student1 = Student("Alice", 20)

print(student1.name)
```

---

## Methods

Methods define object behavior.

```python
class Student:

    def __init__(self, name):
        self.name = name

    def greet(self):
        print("Hello", self.name)

student = Student("Alice")

student.greet()
```

---

## Encapsulation

Encapsulation restricts direct access to internal data.

```python
class BankAccount:

    def __init__(self):
        self.__balance = 1000

    def display(self):
        print(self.__balance)

account = BankAccount()

account.display()
```

Private members begin with double underscores (`__`).

---

## Inheritance

Inheritance enables one class to acquire properties and methods from another class.

```python
class Animal:

    def sound(self):
        print("Animal Sound")

class Dog(Animal):

    def bark(self):
        print("Bark")

dog = Dog()

dog.sound()

dog.bark()
```

Advantages include:

- Code reuse
- Better organization
- Reduced duplication

---

## Polymorphism

Polymorphism allows the same method to behave differently depending on the object.

```python
class Dog:

    def speak(self):
        print("Bark")

class Cat:

    def speak(self):
        print("Meow")

animals = [Dog(), Cat()]

for animal in animals:
    animal.speak()
```

---

## Abstraction

Abstraction hides implementation details while exposing only essential functionality.

```python
from abc import ABC, abstractmethod

class Shape(ABC):

    @abstractmethod
    def area(self):
        pass

class Circle(Shape):

    def area(self):
        return 3.14 * 5 * 5
```

---

# Collections

Python offers several built-in collection data types.

## Lists

Lists are ordered and mutable.

```python
numbers = [10, 20, 30]

numbers.append(40)

numbers.remove(20)

print(numbers)
```

Common methods:

- append()
- extend()
- insert()
- remove()
- pop()
- sort()
- reverse()
- clear()

---

## Tuples

Tuples are ordered but immutable.

```python
point = (10, 20)

print(point[0])
```

---

## Sets

Sets store unique elements.

```python
numbers = {1, 2, 3, 4}

numbers.add(5)

numbers.remove(2)
```

Useful for removing duplicate values.

---

## Dictionaries

Dictionaries store key-value pairs.

```python
student = {

    "name": "Alice",

    "age": 20,

    "marks": 95

}

print(student["name"])
```

Adding values:

```python
student["city"] = "Bangalore"
```

Removing values:

```python
student.pop("age")
```

Looping through a dictionary:

```python
for key, value in student.items():
    print(key, value)
```

---

# Iterators

An iterator is an object that allows sequential traversal of elements.

```python
numbers = [1, 2, 3]

iterator = iter(numbers)

print(next(iterator))

print(next(iterator))

print(next(iterator))
```

Once all elements are consumed, Python raises `StopIteration`.

---

# Generators

Generators produce values lazily, one at a time, using the `yield` keyword.

```python
def count():

    for i in range(5):
        yield i

generator = count()

for value in generator:
    print(value)
```

Advantages:

- Lower memory usage
- Faster processing of large datasets
- Suitable for streaming data

---

# Useful Built-in Functions

Python includes many useful built-in functions.

```python
numbers = [5, 10, 15]

print(len(numbers))

print(max(numbers))

print(min(numbers))

print(sum(numbers))

print(sorted(numbers))

print(abs(-25))
```

Other commonly used built-ins include:

- type()
- input()
- print()
- id()
- zip()
- enumerate()
- map()
- filter()
- any()
- all()
- isinstance()
- round()

---

# Best Practices

Following best practices improves readability, maintainability, and reliability.

- Use meaningful variable names.
- Follow the PEP 8 style guide.
- Keep functions small and focused.
- Avoid global variables whenever possible.
- Handle exceptions appropriately.
- Write comments only when necessary.
- Prefer list comprehensions where appropriate.
- Use virtual environments for project dependencies.
- Organize code into modules and packages.
- Write unit tests for important functionality.

---

# Common Interview Questions

### What is Python?

Python is a high-level, interpreted, general-purpose programming language known for its readability and simplicity.

### What are Python's major features?

- Simple syntax
- Dynamic typing
- Object-oriented
- Large standard library
- Cross-platform compatibility
- Automatic memory management

### What is the difference between a list and a tuple?

Lists are mutable, whereas tuples are immutable.

### What is the difference between `==` and `is`?

`==` compares values, while `is` compares object identities.

### What is the difference between `append()` and `extend()`?

`append()` adds a single object to a list, whereas `extend()` adds multiple elements from another iterable.

### What is recursion?

Recursion is a programming technique in which a function calls itself until a base condition is met.

### What is a generator?

A generator is a special function that produces values one at a time using the `yield` keyword.

### What is exception handling?

Exception handling allows programs to recover gracefully from runtime errors using `try`, `except`, `else`, and `finally`.

---

# Summary

Python is one of the most influential and widely adopted programming languages due to its simplicity, flexibility, and extensive ecosystem. It supports multiple programming paradigms, making it suitable for beginners, researchers, and professional software developers alike. Core concepts such as variables, data types, control structures, functions, modules, object-oriented programming, file handling, exception handling, and collections provide a strong foundation for building reliable applications.

Python's extensive standard library, combined with thousands of third-party packages, enables developers to create solutions in diverse domains including web development, artificial intelligence, machine learning, data science, automation, cybersecurity, cloud computing, and scientific research. By following best coding practices and understanding these core concepts, programmers can build efficient, maintainable, and scalable software applications.