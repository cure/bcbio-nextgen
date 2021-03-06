"""Structural variant detection with the Manta caller from Illumina.

https://github.com/Illumina/manta
"""
import os
import sys

from bcbio import utils
from bcbio.bam import ref
from bcbio.distributed.transaction import file_transaction
from bcbio.pipeline import datadict as dd
from bcbio.variation import vcfutils
from bcbio.provenance import do, programs
from bcbio.structural import shared

def run(items):
    """Perform detection of structural variations with Manta.
    """
    paired = vcfutils.get_paired(items)
    data = paired.tumor_data if paired else items[0]
    work_dir = _sv_workdir(data)
    variant_file = _get_out_file(work_dir, paired)
    if not utils.file_exists(variant_file):
        with file_transaction(data, work_dir) as tx_work_dir:
            utils.safe_makedir(tx_work_dir)
            tx_workflow_file = _prep_config(items, paired, tx_work_dir)
            _run_workflow(items, paired, tx_workflow_file, tx_work_dir)
    assert utils.file_exists(variant_file), "Manta finished without output file %s" % variant_file
    out = []
    for data in items:
        if "sv" not in data:
            data["sv"] = []
        final_vcf = shared.finalize_sv(variant_file, data, items)
        data["sv"].append({"variantcaller": "manta", "vrn_file": final_vcf})
        out.append(data)
    return out

def _get_out_file(work_dir, paired):
    """Retrieve manta output variant file, depending on analysis.
    """
    if paired:
        if paired.normal_bam:
            base_file = "somaticSV.vcf.gz"
        else:
            base_file = "tumorSV.vcf.gz"
    else:
        base_file = "diploidSV.vcf.gz"
    return os.path.join(work_dir, "results", "variants", base_file)

def _run_workflow(items, paired, workflow_file, work_dir):
    """Run manta analysis inside prepared workflow directory.
    """
    utils.remove_safe(os.path.join(work_dir, "workspace"))
    data = paired.tumor_data if paired else items[0]
    cmd = [sys.executable, workflow_file, "-m", "local", "-j", dd.get_num_cores(data)]
    do.run(cmd, "Run manta SV analysis")
    utils.remove_safe(os.path.join(work_dir, "workspace"))

def _prep_config(items, paired, work_dir):
    """Run initial configuration, generating a run directory for Manta.
    """
    assert utils.which("configManta.py"), "Could not find installed configManta.py"
    out_file = os.path.join(work_dir, "runWorkflow.py")
    if not utils.file_exists(out_file) or _out_of_date(out_file):
        cmd = [sys.executable, os.path.realpath(utils.which("configManta.py"))]
        if paired:
            if paired.normal_bam:
                cmd += ["--normalBam=%s" % paired.normal_bam, "--tumorBam=%s" % paired.tumor_bam]
            else:
                cmd += ["--tumorBam=%s" % paired.tumor_bam]
        else:
            cmd += ["--bam=%s" % dd.get_align_bam(data) for data in items]
        data = paired.tumor_data if paired else items[0]
        cmd += ["--referenceFasta=%s" % dd.get_ref_file(data), "--runDir=%s" % work_dir]
        if dd.get_coverage_interval(data) not in ["genome"]:
            cmd += ["--exome"]
        for region in _maybe_limit_chromosomes(data):
            cmd += ["--region", region]
        do.run(cmd, "Configure manta SV analysis")
    return out_file

def _maybe_limit_chromosomes(data):
    """Potentially limit chromosomes to avoid problematically named HLA contigs.

    HLAs have ':' characters in them which confuse downstream processing. If
    we have no problematic chromosomes we don't limit anything.
    """
    std_chroms = []
    prob_chroms = []
    for contig in ref.file_contigs(dd.get_ref_file(data)):
        if contig.name.find(":") > 0:
            prob_chroms.append(contig.name)
        else:
            std_chroms.append(contig.name)
    if len(prob_chroms) > 0:
        return std_chroms
    else:
        return []

def _sv_workdir(data):
    return os.path.join(
        data["dirs"]["work"], "structural", dd.get_sample_name(data), "manta")

def _out_of_date(rw_file):
    """Check if a run workflow file points to an older version of manta and needs a refresh.
    """
    with open(rw_file) as in_handle:
        for line in in_handle:
            if line.startswith("sys.path.append"):
                file_version = line.split("/lib/python")[0].split("Cellar/manta/")[-1]
                if file_version != programs.get_version_manifest("manta"):
                    return True
    return False
