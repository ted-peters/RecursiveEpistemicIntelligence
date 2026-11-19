"""Fresh measurement-ID validation cases authored before running either arm."""
from .paired_values import Case

CASES = (
    Case("inspection-repeats",
         "Trial 1 found A detected 89% of faults and B detected 77%. "
         "Trial 2 found A detected 66% and B detected 84%. "
         "A required 5 labor hours and B required 12.",
         "A detected at least 73% in both trials.",
         ("Choose the option detecting at least 73% in every trial.",
          "Choose the option requiring fewer labor hours."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("harvest-repeats",
         "Field 1 found A increased yield by 11% and B increased yield by 4%. "
         "Field 2 found A decreased yield by 2% and B increased yield by 3%. "
         "A required 7 labor hours and B required 18.",
         "A increased yield in both fields.",
         ("Choose the option increasing yield in each field.",
          "Choose the option requiring fewer labor hours."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("ventilation-repeats",
         "A reduced energy use by 6% in trial 1 and increased it by 2% in trial 2. "
         "B reduced energy use by 3% in trial 1 and by 7% in trial 2. "
         "A cost 29 credits and B cost 44.",
         "A delivered savings in both trials.",
         ("Choose the option delivering energy savings in every trial.",
          "Choose the option with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("classification-repeats",
         "Trial 1 found A classified 85% correctly and B classified 78% correctly. "
         "Trial 2 found A classified 91% correctly and B classified 95% correctly. "
         "A used 64 energy units and B used 37.",
         "A classified at least 82% correctly in both trials.",
         ("Choose the option classifying at least 82% correctly in each trial.",
          "Choose the option using fewer energy units."),
         "supported", ("A", "B"), (1, 2)),
    Case("weekly-parcels",
         "A shipped 32 parcels on Monday and 44 on Tuesday. "
         "B shipped 51 parcels on Monday and 16 on Tuesday. "
         "Neither option measured noise.",
         "A shipped more parcels across both days.",
         ("Choose the option shipping more parcels across both days.",
          "Choose the quieter option. Defer if unmeasured."),
         "supported", ("A", "defer"), (1, 2)),
    Case("room-comparison",
         "A reduced room temperature by 2 degrees using 57 energy units. "
         "B reduced room temperature by 8 degrees using 118 energy units. "
         "Maintenance costs were not measured.",
         "B has lower maintenance costs.",
         ("Choose the option with the greatest temperature reduction.",
          "Choose the option with lower maintenance costs. Defer if unmeasured."),
         "unknown", ("B", "defer"), (3,)),
)
