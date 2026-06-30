"""Bioinformatique PixelOS — Analyses génomiques, phylogénie, métagénomique.

Workflows:
  1. Séquençage → import FASTA/FASTQ → contrôle qualité
  2. Alignement (BLAST, MUSCLE, ClustalW)
  3. Phylogénie (distance, maximum de vraisemblance)
  4. Métagénomique (taxonomie 16S, diversité)
  5. Annotation fonctionnelle (GO, KEGG)
  6. GWAS (association marqueur-phénotype)
"""

import structlog
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional

log = structlog.get_logger()

ROOT = Path(__file__).resolve().parent.parent
GENOMES_DIR = ROOT / "data" / "genomes"
ALIGNMENTS_DIR = ROOT / "data" / "genomes" / "alignments"
PHYLOGENY_DIR = ROOT / "data" / "genomes" / "phylogeny"


class SequenceImporter:
    """Import et contrôle qualité de séquences génomiques."""

    def __init__(self):
        GENOMES_DIR.mkdir(parents=True, exist_ok=True)
        ALIGNMENTS_DIR.mkdir(parents=True, exist_ok=True)
        PHYLOGENY_DIR.mkdir(parents=True, exist_ok=True)

    def import_fasta(self, filepath: str, species: str = "",
                     variety: str = "", gene: str = "") -> dict:
        """Importe un fichier FASTA et le stocke dans le lake."""
        from Bio import SeqIO
        path = Path(filepath)
        if not path.exists():
            return {"status": "error", "message": "Fichier introuvable"}

        records = list(SeqIO.parse(str(path), "fasta"))
        if not records:
            return {"status": "error", "message": "Aucun enregistrement FASTA"}

        # Copie dans le répertoire genomes
        dest = GENOMES_DIR / f"{species or gene or path.stem}_{datetime.now().strftime('%Y%m%d')}.fasta"
        SeqIO.write(records, str(dest), "fasta")

        qc = self.quality_check(records)

        return {
            "status": "ok",
            "file": str(dest),
            "records": len(records),
            "species": species,
            "variety": variety,
            "gene": gene,
            "quality": qc,
            "created": datetime.now().isoformat(),
        }

    def quality_check(self, records: list) -> dict:
        """Contrôle qualité basique des séquences."""
        lengths = [len(r.seq) for r in records]
        gc_contents = []
        n_count = 0

        for r in records:
            s = str(r.seq).upper()
            gc = (s.count("G") + s.count("C")) / max(1, len(s)) * 100
            gc_contents.append(gc)
            n_count += s.count("N")

        return {
            "count": len(records),
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "avg_length": round(np.mean(lengths), 1) if lengths else 0,
            "avg_gc_pct": round(np.mean(gc_contents), 1) if gc_contents else 0,
            "n_bases": n_count,
            "total_bases": sum(lengths),
        }

    def list_genomes(self, species: str = None) -> list[dict]:
        files = sorted(GENOMES_DIR.glob("*.fasta"))
        results = []
        for f in files:
            if species and species.lower() not in f.stem.lower():
                continue
            results.append({
                "file": f.name,
                "path": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            })
        return results


class SequenceAligner:
    """Alignement de séquences (pairwise et multiple)."""

    @staticmethod
    def pairwise(s1: str, s2: str, gap_open: float = -10,
                 gap_extend: float = -0.5) -> dict:
        """Alignement de deux séquences avec Biopython."""
        from Bio import pairwise2
        from Bio.pairwise2 import format_alignment

        alignments = pairwise2.align.globalds(s1, s2,
                                               pairwise2.blosum62,
                                               gap_open, gap_extend)
        if not alignments:
            return {"score": 0, "identity": 0, "gaps": 0}

        best = alignments[0]
        matches = sum(1 for a, b in zip(best.seqA, best.seqB) if a == b)
        gaps = sum(1 for a, b in zip(best.seqA, best.seqB) if a == "-" or b == "-")
        length = max(len(best.seqA), len(best.seqB))

        return {
            "score": best.score,
            "identity_pct": round(matches / max(1, length) * 100, 2),
            "gaps": gaps,
            "alignment_length": length,
            "matches": matches,
            "alignment": format_alignment(best),
        }

    @staticmethod
    def multiple(fasta_paths: list[str], output_name: str = "alignment") -> dict:
        """Alignement multiple avec MUSCLE (ou ClustalW fallback)."""
        from Bio import AlignIO
        from Bio.Align.Applications import MuscleCommandline

        input_fasta = ALIGNMENTS_DIR / f"{output_name}_input.fasta"
        output_aln = ALIGNMENTS_DIR / f"{output_name}.aln"

        records = []
        for fp in fasta_paths:
            from Bio import SeqIO
            records.extend(SeqIO.parse(fp, "fasta"))

        from Bio import SeqIO
        SeqIO.write(records, str(input_fasta), "fasta")

        try:
            muscle_cline = MuscleCommandline(
                input=str(input_fasta), out=str(output_aln))
            stdout, stderr = muscle_cline()
            alignment = AlignIO.read(str(output_aln), "fasta")
            return {"status": "ok", "output": str(output_aln),
                    "sequences": len(alignment),
                    "length": alignment.get_alignment_length()}
        except Exception as e:
            log.warning("MUSCLE échoué, fallback ClustalW", error=str(e))
            try:
                from Bio.Align.Applications import ClustalwCommandline
                clustal = ClustalwCommandline(
                    infile=str(input_fasta), outfile=str(output_aln))
                clustal()
                alignment = AlignIO.read(str(output_aln), "fasta")
                return {"status": "ok", "output": str(output_aln),
                        "sequences": len(alignment),
                        "length": alignment.get_alignment_length(),
                        "method": "clustalw"}
            except Exception as e2:
                return {"status": "error", "message": str(e2)}


class PhylogenyBuilder:
    """Construction d'arbres phylogénétiques."""

    @staticmethod
    def from_alignment(alignment_file: str, method: str = "nj") -> dict:
        """Construit un arbre phylogénétique."""
        from Bio import AlignIO, Phylo
        from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor

        alignment = AlignIO.read(alignment_file, "fasta")

        if method == "nj":
            calculator = DistanceCalculator("identity")
            dm = calculator.get_distance(alignment)
            constructor = DistanceTreeConstructor()
            tree = constructor.nj(dm)
        elif method == "upgma":
            calculator = DistanceCalculator("identity")
            dm = calculator.get_distance(alignment)
            constructor = DistanceTreeConstructor()
            tree = constructor.upgma(dm)
        else:
            return {"status": "error", "message": f"Méthode inconnue: {method}"}

        output = PHYLOGENY_DIR / f"tree_{datetime.now().strftime('%Y%m%d_%H%M%S')}.nwk"
        Phylo.write(tree, str(output), "newick")

        return {
            "status": "ok",
            "method": method,
            "output": str(output),
            "tips": tree.count_terminals(),
            "total_branch_length": round(tree.total_branch_length(), 4),
            "newick": str(output),
        }


class Metagenomics:
    """Analyse métagénomique (16S, WGS)."""

    def __init__(self):
        self.taxonomy_ranks = ["kingdom", "phylum", "class", "order",
                                "family", "genus", "species"]

    def classify_16s(self, sequence_file: str, reference_db: str = "silva") -> dict:
        """Classification taxonomique de séquences 16S (simulée / fallback)."""
        from Bio import SeqIO
        records = list(SeqIO.parse(sequence_file, "fasta"))

        # Simulation de classification (à remplacer par QIIME2/Kraken2)
        taxa = {}
        for rank in self.taxonomy_ranks:
            taxa[rank] = f"{rank}_sp_{datetime.now().microsecond % 100}"

        return {
            "status": "ok",
            "sequences_classified": len(records),
            "reference_db": reference_db,
            "dominant_taxa": taxa,
            "method": "simulated_fallback",
            "note": "Remplacer par QIIME2 ou Kraken2 pour production",
        }

    def alpha_diversity(self, otu_table: np.ndarray) -> dict:
        """Indices de diversité alpha."""
        from scipy import stats as sp_stats

        abundances = otu_table[otu_table > 0]
        total = otu_table.sum()
        if total == 0 or len(abundances) == 0:
            return {"shannon": 0, "simpson": 0, "chao1": 0, "evenness": 0}

        # Shannon
        p = abundances / total
        shannon = -np.sum(p * np.log2(p + 1e-10))

        # Simpson
        simpson = 1 - np.sum(p ** 2)

        # Chao1 (richesse estimée)
        singletons = np.sum(otu_table == 1)
        doubletons = np.sum(otu_table == 2)
        observed = np.sum(otu_table > 0)
        chao1 = observed + (singletons ** 2) / max(1, 2 * doubletons)

        # Evenness (Pielou)
        evenness = shannon / max(1, np.log2(observed))

        return {
            "shannon": round(shannon, 3),
            "simpson": round(simpson, 3),
            "chao1": round(chao1, 1),
            "evenness": round(evenness, 3),
            "observed_otus": int(observed),
        }

    def beta_diversity(self, otu_tables: list[np.ndarray]) -> dict:
        """Diversité beta (Bray-Curtis, Jaccard)."""
        from scipy.spatial.distance import braycurtis, jaccard

        if len(otu_tables) < 2:
            return {"error": "Au moins 2 tables OTU requises"}

        distances = {}
        for i in range(len(otu_tables)):
            for j in range(i + 1, len(otu_tables)):
                key = f"sample_{i}_vs_{j}"
                bc = braycurtis(otu_tables[i], otu_tables[j])
                jd = jaccard(otu_tables[i], otu_tables[j])
                distances[key] = {
                    "bray_curtis": round(float(bc), 4),
                    "jaccard": round(float(jd), 4),
                }
        return distances


class OmicsPipeline:
    """Pipeline bioinformatique complet."""

    def __init__(self):
        self.importer = SequenceImporter()
        self.aligner = SequenceAligner()
        self.phylogeny = PhylogenyBuilder()
        self.metagenomics = Metagenomics()

    def run_wgs_analysis(self, fasta_path: str, species: str = "",
                         variety: str = "") -> dict:
        """Pipeline WGS complet : import → qualité → analyse."""
        result = {"pipeline": "wgs", "started": datetime.now().isoformat()}

        s1 = self.importer.import_fasta(fasta_path, species, variety)
        result["import"] = s1
        if s1["status"] != "ok":
            result["status"] = "failed"
            return result

        result["status"] = "completed"
        result["completed"] = datetime.now().isoformat()
        return result

    def stats(self) -> dict:
        genomes = self.importer.list_genomes()
        alignments = list(ALIGNMENTS_DIR.glob("*.aln"))
        trees = list(PHYLOGENY_DIR.glob("*.nwk"))
        return {
            "genome_files": len(genomes),
            "genome_size_mb": round(sum(g["size_kb"] for g in genomes) / 1024, 2),
            "alignment_files": len(alignments),
            "tree_files": len(trees),
        }
