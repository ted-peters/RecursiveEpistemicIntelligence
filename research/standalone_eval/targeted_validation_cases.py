"""New public development cases frozen before testing targeted extraction."""
from .paired_values import Case

CASES = (
    Case("packaging-repeat",
         "Run 1 recorded 91% intact items for A and 77% for B. "
         "Run 2 recorded 63% intact items for A and 81% for B. "
         "Packaging costs were 14 credits for A and 22 for B.",
         "A achieved at least 70% intact items in both runs.",
         ("Choose the option achieving at least 70% intact items in every trial.",
          "Choose the option with lower packaging cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("training-repeat",
         "In site 1, A increased completed tasks by 6% and B increased them by 4%. "
         "In site 2, A decreased completed tasks by 1% and B increased them by 2%. "
         "A required 9 training hours and B required 15.",
         "Both sites recorded an increase for A.",
         ("Choose the option increasing completed tasks in each trial.",
          "Choose the option requiring fewer training hours."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("shipping-weeks",
         "A shipped 34 crates in week 1 and 17 in week 2. "
         "B shipped 22 crates in week 1 and 41 in week 2. "
         "A damaged 2 crates and B damaged 6.",
         "B shipped more crates over the two weeks.",
         ("Choose the option shipping more crates over the two weeks.",
          "Choose the option damaging fewer crates."),
         "supported", ("B", "A"), (1, 2)),
    Case("heating-options",
         "A reduced heating energy use by 5% at site 1 and increased it by 2% at site 2. "
         "B reduced heating energy use by 3% at site 1 and by 4% at site 2. "
         "Neither option measured indoor air quality.",
         "B improved indoor air quality.",
         ("Choose the option delivering energy savings in every trial.",
          "Choose the option improving indoor air quality more. Defer if unmeasured."),
         "unknown", ("B", "defer"), (3,)),
    Case("service-targets",
         "Trial 1 found A resolved 84% of requests and B resolved 79%. "
         "Trial 2 found A resolved 86% of requests and B resolved 92%. "
         "A cost 45 credits and B cost 31 credits.",
         "A resolved at least 80% of requests in both trials.",
         ("Choose the option resolving at least 80% in each trial.",
          "Choose the option with lower cost."),
         "supported", ("A", "B"), (1, 2)),
    Case("delivery-noise",
         "A completed 29 deliveries on Monday and 36 on Tuesday. "
         "B completed 41 deliveries on Monday and 13 on Tuesday. "
         "Neither option measured neighborhood noise.",
         "A completed more deliveries across both days.",
         ("Choose the option completing more deliveries across both days.",
          "Choose the quieter option. Defer if noise is unmeasured."),
         "supported", ("A", "defer"), (1, 2)),
)
