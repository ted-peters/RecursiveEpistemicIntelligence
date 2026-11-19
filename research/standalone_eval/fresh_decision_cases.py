"""Fresh public development cases authored after the compact prompt was fixed."""
from .paired_values import Case

CASES = (
    Case("parcel-choice",
         "Plan A delivered 72 parcels on Monday and 18 on Tuesday. "
         "Plan B delivered 55 parcels on Monday and 49 on Tuesday. "
         "A had 1 damaged parcel and B had 4.",
         "A delivered more parcels across both days.",
         ("Choose the plan with more deliveries across both days.",
          "Choose the plan with fewer damaged parcels."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("pool-hours",
         "Schedule A served 24 morning swimmers and 70 evening swimmers. "
         "Schedule B served 62 morning swimmers and 35 evening swimmers. "
         "Neither schedule measured satisfaction.",
         "B served more morning swimmers than A.",
         ("Choose the schedule serving more morning swimmers.",
          "Choose the schedule with greater measured satisfaction. Defer if unmeasured."),
         "supported", ("B", "defer"), (1, 2)),
    Case("filter-choice",
         "Trial 1 found filter A removed 82% of particles and B removed 68%. "
         "Trial 2 found filter A removed 51% of particles and B removed 74%. "
         "Replacement costs were 30 credits for A and 18 for B.",
         "A removed more particles than B in both trials.",
         ("Choose the filter with lower replacement cost.",
          "Choose the filter that removed at least 60% in each trial."),
         "contradicted", ("B", "B"), (1, 2)),
    Case("room-cooling",
         "Test A lowered room temperature by 4 degrees while using 90 energy units. "
         "Test B lowered room temperature by 7 degrees while using 140 energy units. "
         "Noise levels were not measured.",
         "A produced less noise than B.",
         ("Choose the test with the greatest temperature reduction.",
          "Choose the test using fewer energy units."),
         "unknown", ("B", "A"), (3,)),
    Case("crop-trials",
         "In field 1, treatment A increased yield by 8% and B increased it by 3%. "
         "In field 2, treatment A decreased yield by 2% and B increased it by 3%. "
         "A cost 12 credits and B cost 20 credits.",
         "A increased yield in both fields.",
         ("Choose the treatment increasing yield in each field.",
          "Choose the treatment with lower cost."),
         "contradicted", ("B", "A"), (1, 2)),
    Case("repair-options",
         "Option A repaired 19 devices in week 1 and 28 in week 2. "
         "Option B repaired 31 devices in week 1 and 11 in week 2. "
         "Long-term failure rates were not tracked.",
         "A repaired more devices over both weeks.",
         ("Choose the option with more repairs across both weeks.",
          "Choose the option with fewer long-term failures. Defer if unmeasured."),
         "supported", ("A", "defer"), (1, 2)),
)
