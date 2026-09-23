from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .orchestrator import bootstrap_environment, check_environment, preview_simi_terms, run_job


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orchestrateur Python pour IRaMuTeQ Lite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Verifier Python/R et le runner R.")
    check_parser.add_argument("--rscript", help="Chemin explicite vers Rscript.")

    bootstrap_parser = subparsers.add_parser(
        "bootstrap", help="Verifier et installer les packages R necessaires."
    )
    bootstrap_parser.add_argument("--rscript", help="Chemin explicite vers Rscript.")
    bootstrap_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verifier sans installation automatique.",
    )

    run_parser = subparsers.add_parser("run", help="Lancer une analyse batch via Python -> R.")
    run_parser.add_argument("--input", required=True, help="Chemin du corpus texte.")
    run_parser.add_argument("--config", required=True, help="Chemin du JSON de configuration.")
    run_parser.add_argument("--output-root", help="Dossier parent des jobs.")
    run_parser.add_argument("--job-id", help="Identifiant de job optionnel.")
    run_parser.add_argument("--rscript", help="Chemin explicite vers Rscript.")

    simi_terms_parser = subparsers.add_parser(
        "preview-simi-terms", help="Calculer la liste exacte des termes de similitudes."
    )
    simi_terms_parser.add_argument("--input", required=True, help="Chemin du corpus texte.")
    simi_terms_parser.add_argument("--config", required=True, help="Chemin du JSON de configuration.")
    simi_terms_parser.add_argument("--output-root", help="Dossier parent des jobs.")
    simi_terms_parser.add_argument("--job-id", help="Identifiant de job optionnel.")
    simi_terms_parser.add_argument("--rscript", help="Chemin explicite vers Rscript.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "check":
        payload = check_environment(rscript_path=args.rscript)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "bootstrap":
        payload = bootstrap_environment(
            rscript_path=args.rscript,
            auto_install=not args.check_only,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("success") else 1

    if args.command == "preview-simi-terms":
        config_path = Path(args.config).expanduser().resolve()
        input_path = Path(args.input).expanduser().resolve()
        output_root = Path(args.output_root).expanduser().resolve() if args.output_root else None
        config = json.loads(config_path.read_text(encoding="utf-8"))
        payload = preview_simi_terms(
            corpus_path=input_path,
            config=config,
            output_root=output_root,
            job_id=args.job_id,
            rscript_path=args.rscript,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("success") else 1

    config_path = Path(args.config).expanduser().resolve()
    input_path = Path(args.input).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else None
    config = json.loads(config_path.read_text(encoding="utf-8"))

    payload = run_job(
        corpus_path=input_path,
        config=config,
        output_root=output_root,
        job_id=args.job_id,
        rscript_path=args.rscript,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
