"""Sample question files teachers can download and copy. One per question type; the same layout works in .txt, .docx and .pdf."""

RULES = """HOW TO WRITE THE FILE
- Number every question: Q1.  Q2.  Q3.  (1.  2.  3.  or Q1)  Q2)  also work). Numbers must run in order.
- Write the answer on a new line that starts with  Answer:
  Everything after "Answer:" is the answer - including any explanation lines - until the next question number.
- Section headings (Section A - ...), page numbers and repeated page headings are ignored.
- To add notes/formulas at the end, start them with "Quick Revision" (or "End of questions"); everything after that line is ignored.
- Use ONE question type per file and choose that type when you upload.
"""

SAMPLES = {
    1: ("1 Mark (multiple choice)", """Laws of Motion - 1 Mark Questions
Section A - Basic Concepts

Q1. Who formulated the three laws of motion?
A) Albert Einstein
B) Isaac Newton
C) Galileo Galilei
D) Johannes Kepler
Answer: B) Isaac Newton
Isaac Newton formulated the three laws of motion.

Q2. The SI unit of force is:
A) Joule
B) Watt
C) Newton
D) Pascal
Answer: C) Newton
Force is measured in newtons (N).

Section B - Numerical Questions

Q3. A force of 10 N acts on a body of mass 2 kg. Its acceleration is:
A) 2 m/s2
B) 5 m/s2
C) 10 m/s2
D) 20 m/s2
Answer: B) 5 m/s2
a = F/m = 10/2 = 5 m/s2.

Quick Revision
F = ma, p = mv
"""),
    2: ("2 Marks (short answer)", """Laws of Motion - 2 Mark Questions

Q1. State Newton's first law of motion.
Answer: A body stays at rest or in uniform motion in a straight line unless an external unbalanced force acts on it.

Q2. Define momentum. Write its SI unit.
Answer: Momentum is the product of mass and velocity (p = mv).
SI unit: kg m/s.

Q3. A force of 20 N acts on a body of mass 4 kg. Find its acceleration.
Answer: a = F/m = 20/4 = 5 m/s2.
"""),
    3: ("3 Marks (short explanation)", """Laws of Motion - 3 Mark Questions

Q1. State Newton's second law and write its mathematical form.
Answer: The rate of change of momentum of a body is directly proportional to the applied force and takes place in the direction of the force.
Mathematically, F = ma for a body of constant mass.

Q2. Why do passengers fall forward when a moving bus stops suddenly? Explain with the law involved.
Answer: This is the law of inertia (Newton's first law).
The feet stop with the bus, but the upper body tends to stay in motion.
So the passenger is thrown forward.
"""),
    4: ("4 Marks (numerical / derivation)", """Laws of Motion - 4 Mark Questions

Q1. A body of mass 5 kg is moving at 10 m/s. A constant force of 20 N acts on it for 3 s. Find the final velocity.
Answer: a = F/m = 20/5 = 4 m/s2.
v = u + at = 10 + 4 x 3 = 22 m/s.
Final velocity = 22 m/s.

Q2. Show that Newton's second law gives the first law.
Answer: F = ma. If F = 0 then a = 0.
So the velocity does not change: the body stays at rest or moves with uniform velocity.
This is Newton's first law.
"""),
    5: ("5 Marks (long answer / derivation)", """Laws of Motion - 5 Mark Questions

Q1. State the law of conservation of momentum and derive it from Newton's third law.
Answer: Statement: if no external force acts on a system, its total momentum stays constant.
Derivation: take two bodies A and B colliding for a time t.
Force on A by B = - force on B by A (third law).
So change in momentum of A = - change in momentum of B.
Hence total momentum before = total momentum after.

Q2. Explain the working of a rocket using Newton's laws.
Answer: Hot gases are pushed out of the rocket backwards (action).
The gases push the rocket forward with an equal force (reaction).
As the rocket's mass decreases and thrust stays large, it keeps accelerating.
"""),
}


def sample_text(n):
    name, body = SAMPLES[n]
    return RULES + "\n" + "=" * 60 + "\nSAMPLE (" + name + ") - copy this layout; delete these instructions in your own file\n" + "=" * 60 + "\n\n" + body
