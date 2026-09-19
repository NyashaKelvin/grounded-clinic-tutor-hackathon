"""Fixed learner-facing texts for each outcome. None of these come from a model."""

NOT_IN_CORPUS = ("The approved Zimbabwe nursing sources in this tutor do not contain enough information "
                 "to answer that reliably.")
CONFLICTING_SOURCES = ("The approved sources contain differing guidance. The relevant sources and the differences "
                       "are shown below. Please verify which edition or protocol your institution currently uses.")
OUT_OF_SCOPE = ("This tutor is designed for nursing education and cannot provide that type of advice. "
                "For a real patient, follow your facility protocol and ask your supervisor, a qualified clinician or a pharmacist.")
OUT_OF_SCOPE_FABRICATION = ("I can't invent or pretend a guideline. This tutor only repeats what its approved Zimbabwe "
                            "sources actually say, and it will say so when they don't cover a question.")
CANNOT_VERIFY = ("I found potentially relevant material, but I could not verify the specific claim from the source text, "
                 "so I won't present it as established guidance. The source passages are shown below so you can read them yourself.")
EMERGENCY = ("This may require immediate clinical escalation. Follow your facility's emergency protocol and involve the "
             "appropriate clinician or supervisor now. This tutor is not an emergency service and cannot help with a live emergency.")
NEEDS_CLARIFICATION = ("I need a little more detail to search the sources. Please name the condition, medicine or procedure "
                       "you want to learn about, for example \"PMTCT infant prophylaxis\" or \"postnatal check for the newborn\".")
PRIVACY_BLOCKED = ("Your message looks like it contains personal patient information ({kinds}). It was NOT sent to the AI "
                   "and nothing was stored. Please remove names, patient numbers, addresses and phone numbers, and ask again in general terms.")
OVERRIDE_NOTICE = ("Note: this tutor can only use its approved sources. It cannot answer from general medical knowledge "
                   "or leave out citations, so those parts of the request were ignored.")
EDUCATION_NOTICE = ("Educational support only. Verify clinical decisions against your current institutional guidelines, "
                    "course material, and instructions from your nurse educator or clinical supervisor.")
PRIVACY_WARNING = ("Do not enter names, patient numbers, addresses, phone numbers, or other identifying patient information. "
                   "Nothing you type is stored by this app.")
UNCALIBRATED = ("The evidence thresholds have not been calibrated on the evaluation set yet, so refusals may be too strict "
                "or too loose. Do not draw conclusions about accuracy until calibration is done.")
