# Compound Triage

A hit-to-lead dashboard for a medicinal chemistry team working on a made-up
kinase target, TKX1. It answers the question a project team asks at every
design meeting: of the molecules we have made, which ones actually work, and
what is stopping the rest?

A compound "works" when it clears every bar in the target product profile:
biochemical potency, cell potency, kinome selectivity, solubility, microsomal
clearance, Caco-2 permeability and a hERG safety margin. Set each bar in the
sidebar and the whole page updates.

The app shows:

- **Headline counts**: compounds made, how many meet every criterion, how many
  miss by exactly one (and which criterion blocks them most often), and the best
  lipophilic ligand efficiency among potent compounds
- **Where compounds drop out**: the survivors after each gate, in the order the
  assay cascade runs them. Hover a bar to see how many failed there and how
  many were never tested
- **Potency vs lipophilicity**: pIC50 against cLogP with LLE diagonals, each
  compound colored by verdict. Click one to open it
- **Closest to a candidate**: the top seven compounds with their structures,
  ranked by criteria met and then by margin
- **Which series clear each bar**: pass rate of tested compounds for each
  chemical series and criterion
- **Is the chemistry getting better?**: compounds made per month, by verdict
- **Compound detail**: the 2D structure, SMILES and computed properties
  (MW, cLogP, TPSA, HBD/HBA, QED, LLE), how far each measurement sits past its
  bar, and the biochemical dose-response curve with replicates and the Hill fit

The data is synthetic. `compounds.py` builds 296 valid molecules by putting
R-groups on four kinase-like scaffolds, and computes their properties with
[RDKit](https://www.rdkit.org/). The assay results come from an additive model
(scaffold + R1 + R2 effects, plus noise) with realistic trade-offs: lipophilic
compounds are more potent but less soluble, cleared faster and more likely to
block hERG; basic amines add hERG risk; polar compounds lose permeability and
so lose potency in cells. As in a real project, only biochemically active
compounds were run in cells, and only cell-active ones were profiled for ADME
and safety, so many compounds are never measured on the later assays.

Built with [Dash](https://dash.plotly.com/),
[Dash Mantine Components](https://www.dash-mantine-components.com/) and RDKit.

![Screenshot of app](assets/screenshot.png)
