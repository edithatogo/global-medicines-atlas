# Readme

In FHIR R4 the two data models split across two complementary resources that are designed to reference each other:
Medication ← holds the NZULM product data (what the thing is)
MedicationKnowledge ← holds the NZF clinical layer (what to do with it)
They link via MedicationKnowledge.associatedMedication (a Reference to Medication).

NZULM → Medication (R4)
NZULM fieldFHIR R4 pathTypeNotesidMedication.identifierIdentifiersystem: https://nzulm.health.govt.nznameMedication.code.textstringFull trade namegeneric_nameMedication.code.codingCodingsystem: SNOMED CTformMedication.formCodeableConceptSNOMED CT dose form (e.g. 385055001 = Tablet)strengthMedication.ingredient.strengthRationumerator: 500 mg / denominator: 1 tabletgeneric_name (substance)Medication.ingredient.itemCodeableConceptCodeableConceptisActive: true; or Reference(Substance)sponsorMedication.manufacturerReference(Organization)Separate Organization resource per MAHpack_sizeMedication.amountRatioe.g. 90 tablets/packmedsafe_statusextension[medsafe-approval-status]codeNZ extension — no native R4 slotrouteMedicationKnowledge.intendedRouteCodeableConceptRoute doesn't exist on Medication until R5updated_atMedication.meta.lastUpdatedinstantsource_fileMedication.meta.sourceuriGitHub raw file URL as provenance

NZF → MedicationKnowledge (R4)
NZF fieldFHIR R4 pathTypeNotesidMedicationKnowledge.identifierIdentifiersystem: https://nzf.org.nzulm_ref (FK)MedicationKnowledge.associatedMedicationReference(Medication)The core cross-resource linkdrug_nameMedicationKnowledge.code.textstringatc_codeMedicationKnowledge.medicineClassification.classificationCodeableConceptsystem: http://www.whocc.no/atcindicationMedicationKnowledge.administrationGuidelines.indicationCodeableConceptSNOMED CT clinical finding codesdosingMedicationKnowledge.administrationGuidelines.dosageDosageFull FHIR Dosage datatype (timing, dose, route)routeMedicationKnowledge.intendedRouteCodeableConceptSNOMED CT route codescontraindicationsMedicationKnowledge.contraindicationReference⚠ see R4 caveat belowinteractionsMedicationKnowledge.drugInteractionBackboneElement.interactant, .description, .severitymonitoringMedicationKnowledge.monitoringProgramBackboneElement.name, .typefunding_statusextension[pharmac-funding-status]codeNZ extensionrestriction_typeMedicationKnowledge.regulatory.scheduleCodeableConcept.regulatoryAuthority → PHARMAC Organizationpharmac_scheduleextension[pharmac-schedule-ref]stringNZ extension — e.g. "Section H, Subpart 2"pregnancy_categoryextension[pregnancy-category]codeNZ extension — A/B1/B2/B3/C/D/X

NZ-specific extensions required (6)
All should be registered as StructureDefinition resources under a canonical base URL (e.g. https://nzf.org.nz/fhir/StructureDefinition/) and published to the NZ FHIR registry.
On Medication:

medsafe-approval-status — code: Active / Controlled / Discontinued / Under Review
nzulm-product-type — code: Branded / Generic / Biosimilar / Extemporaneous

On MedicationKnowledge:

pharmac-funding-status — code: Funded / Unfunded / Partially Funded
pharmac-schedule-ref — string: human-readable schedule section
pregnancy-category — code: A / B1 / B2 / B3 / C / D / X
restriction-type — code: Unrestricted / Special Authority / Hospital Only / Controlled Drug


One important R4 caveat — contraindications
MedicationKnowledge.contraindication in the base R4 spec references ClinicalUseIssue, which is a resource that only formally arrived in R4B. For strict base R4, the practical options are to encode contraindications as a coded List resource, use a NZ extension with a CodeableConcept array, or note in your IG that R4B compatibility is required for this element. This is one of the strongest arguments for targeting R4B over base R4 if you're building this from scratch.

Supporting resources (no extensions needed)

Organization — one per sponsor/MAH (referenced by Medication.manufacturer), plus one fixed PHARMAC organization (referenced by MedicationKnowledge.regulatory.regulatoryAuthority)
Substance — optional, for active ingredients as first-class resources rather than inline CodeableConcepts
Provenance — maps the GitHub commit SHA to each resource update, giving you a full audit trail via Provenance.entity pointing to the git commit URL

On every push to main that touches any of those paths, the workflow diffs HEAD~1 against HEAD to find only the changed files, then issues a PUT {FHIR_BASE}/{ResourceType}/{id} for each one. Deleted files are skipped rather than issuing a DELETE (safe default — add that if you want tombstoning). Two repo secrets drive it: FHIR_SERVER_BASE_URL and FHIR_SERVER_TOKEN.
Naming convention — files are named {NZMT-ID}-{display-name}.json so they're human-readable in the GitHub file browser but the FHIR server ignores the filename entirely and uses the id field inside the JSON to route the PUT.