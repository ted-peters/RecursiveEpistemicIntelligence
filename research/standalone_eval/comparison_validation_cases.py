"""Public validation cases frozen before comparison; never passed with answer keys."""
from .paired_values import Case

CASES = (
    Case("screening-rates",
         "Trial 1 found A identified 87% of defects and B identified 78%. "
         "Trial 2 found A identified 69% of defects and B identified 82%. "
         "A cost 16 credits and B cost 23 credits.",
         "A identified at least 74% in both trials.",
         ("Choose the option identifying at least 74% in each trial.",
          "Choose the option with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("plant-growth",
         "Field 1 found A increased growth by 9% and B increased growth by 3%. "
         "Field 2 found A decreased growth by 4% and B increased growth by 2%. "
         "A required 6 labor hours and B required 14.",
         "A increased growth in both fields.",
         ("Choose the option increasing growth in every field.",
          "Choose the option requiring fewer labor hours."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("lighting-savings",
         "A reduced energy use by 7% at site 1 and increased it by 3% at site 2. "
         "B reduced energy use by 4% at site 1 and by 6% at site 2. "
         "A cost 33 credits and B cost 48 credits.",
         "A saved energy at both sites.",
         ("Choose the option delivering energy savings in every trial.",
          "Choose the option with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("delivery-counts",
         "A completed 27 deliveries on day 1 and 42 on day 2. "
         "B completed 46 deliveries on day 1 and 14 on day 2. "
         "Neither option measured customer satisfaction.",
         "A completed more deliveries over both days.",
         ("Choose the option completing more deliveries over both days.",
          "Choose the option with greater customer satisfaction. Defer if unmeasured."),
         "supported", ("A", "defer"), (1, 2)),
    Case("accuracy-target",
         "Trial 1 found A classified 86% correctly and B classified 80% correctly. "
         "Trial 2 found A classified 90% correctly and B classified 93% correctly. "
         "A used 58 energy units and B used 39.",
         "A classified at least 83% correctly in both trials.",
         ("Choose the option classifying at least 83% correctly in each trial.",
          "Choose the option using fewer energy units."),
         "supported", ("A", "B"), (1, 2)),
    Case("temperature-choice",
         "A lowered temperature by 3 degrees using 61 energy units. "
         "B lowered temperature by 6 degrees using 102 energy units. "
         "Noise was not measured.",
         "B is quieter than A.",
         ("Choose the option with the greatest temperature reduction.",
          "Choose the option using fewer energy units."),
         "unknown", ("B", "A"), (3,)),
)
