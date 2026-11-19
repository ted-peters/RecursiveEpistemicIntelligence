"""Fresh cases frozen before live validation of text and direction extraction."""
from .paired_values import Case

CASES = (
    Case("seal-threshold",
         "Trial 1 found A sealed 88% of containers and B sealed 76%. "
         "Trial 2 found A sealed 67% and B sealed 85%. "
         "A cost 11 credits and B cost 19 credits.",
         "A sealed at least 75% in both trials.",
         ("Choose the option sealing at least 75% in every trial.",
          "Choose the option with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("orchard-growth",
         "Field 1 recorded A increasing fruit yield by 7% and B increasing it by 2%. "
         "Field 2 recorded A decreasing fruit yield by 3% and B increasing it by 1%. "
         "A required 8 labor hours and B required 13.",
         "A increased yield in both fields.",
         ("Choose the option increasing yield in each field.",
          "Choose the option requiring fewer labor hours."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("water-savings",
         "A reduced water use by 9% in trial 1 and increased it by 4% in trial 2. "
         "B reduced water use by 3% in trial 1 and by 5% in trial 2. "
         "A cost 27 credits and B cost 38.",
         "A reduced water use in both trials.",
         ("Choose the option reducing water use in every trial.",
          "Choose the option with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("thermal-reduction",
         "A reduced heating energy use by 8% at site 1 and increased it by 1% at site 2. "
         "B reduced heating energy use by 2% at site 1 and by 6% at site 2. "
         "Neither option measured indoor humidity.",
         "B improves indoor humidity.",
         ("Choose the option delivering energy savings in each trial.",
          "Choose the option improving indoor humidity more. Defer if unmeasured."),
         "unknown", ("B", "defer"), (3,)),
    Case("sorting-minimum",
         "Trial 1 found A sorted 83% correctly and B sorted 79% correctly. "
         "Trial 2 found A sorted 89% correctly and B sorted 94% correctly. "
         "A used 52 energy units and B used 35.",
         "A sorted at least 81% correctly in both trials.",
         ("Choose the option sorting at least 81% correctly in every trial.",
          "Choose the option using fewer energy units."),
         "supported", ("A", "B"), (1, 2)),
    Case("weekly-output",
         "A completed 38 orders in week 1 and 25 in week 2. "
         "B completed 47 orders in week 1 and 9 in week 2. "
         "Neither option tracked customer satisfaction.",
         "A completed more orders across both weeks.",
         ("Choose the option completing more orders across both weeks.",
          "Choose the option with greater customer satisfaction. Defer if unmeasured."),
         "supported", ("A", "defer"), (1, 2)),
)
