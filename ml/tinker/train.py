"""Fine-tune the duck on Tinker (LoRA, supervised) from ml/tinker/data/train.jsonl.

    uv run python ml/tinker/train.py --dry-run          # build every example, print token counts, no API calls
    uv run python ml/tinker/train.py                    # train (needs TINKER_API_KEY in .env)

Only the duck's reply tokens are trained on; the system prompt and conversation are masked. The run's hyperparameters,
loss history and the checkpoint path are saved to ml/tinker/runs/<name>.json.
The frozen eval set is verified first, and a few training dialogues are held out as a validation loss check.
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from duckwalk import config  # noqa: E402,F401  (loads .env)

import build_eval  # noqa: E402
from tinker_sampler import renderer_name  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RUNS = HERE / "runs"
VAL_FRACTION = 0.05
PRICE_UPPER_BOUND_PER_M = 1.463  # $/M training tokens for Qwen3.5-9B: the 4B costs less (its own price isn't listed)


def load_examples():
    return [json.loads(line) for line in (DATA / "train.jsonl").read_text().splitlines()]


def split_by_dialogue(examples, seed=3):
    ids = sorted({e["dialogue"] for e in examples})
    random.Random(seed).shuffle(ids)
    val_ids = set(ids[: max(1, int(len(ids) * VAL_FRACTION))])
    return [e for e in examples if e["dialogue"] not in val_ids], [e for e in examples if e["dialogue"] in val_ids]


def make_datums(examples, base_model, max_length):
    from tinker_cookbook.renderers import TrainOnWhat, get_renderer
    from tinker_cookbook.supervised.data import conversation_to_datum
    from transformers import AutoTokenizer

    renderer = get_renderer(renderer_name(base_model), AutoTokenizer.from_pretrained(base_model))
    return [conversation_to_datum(e["messages"], renderer, max_length=max_length,
                                  train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE) for e in examples]


def mean_loss(metrics: dict) -> float | None:
    for key, value in metrics.items():
        if key.startswith("loss"):
            return float(value)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--name", default="qwen35-4b-duck-v1")
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    build_eval.verify_frozen()
    train, val = split_by_dialogue(load_examples())
    train_data, val_data = make_datums(train, args.base, args.max_length), make_datums(val, args.base, args.max_length)
    tokens = sum(d.model_input.length for d in train_data)
    steps_per_epoch = math.ceil(len(train_data) / args.batch)
    total_steps = steps_per_epoch * args.epochs
    est = tokens * args.epochs / 1e6 * PRICE_UPPER_BOUND_PER_M
    print(f"{len(train_data)} train + {len(val_data)} validation examples, {tokens:,} tokens per epoch, "
          f"{total_steps} steps ({args.epochs} epochs of {steps_per_epoch}), upper-bound cost ~${est:.2f}")
    if args.dry_run:
        return 0

    import tinker

    service = tinker.ServiceClient()
    tc = service.create_lora_training_client(base_model=args.base, rank=args.rank, user_metadata={"name": args.name})
    history, rng, step, started = [], random.Random(5), 0, time.time()
    for epoch in range(args.epochs):
        order = list(range(len(train_data)))
        rng.shuffle(order)
        for i in range(0, len(order), args.batch):
            batch = [train_data[j] for j in order[i:i + args.batch]]
            lr = args.lr * (1 - 0.9 * step / max(1, total_steps - 1))  # linear decay to 10%
            fwd = tc.forward_backward(batch, "cross_entropy")
            opt = tc.optim_step(tinker.AdamParams(learning_rate=lr))
            loss = mean_loss(fwd.result().metrics)
            opt.result()
            history.append({"step": step, "epoch": epoch, "lr": lr, "loss": loss})
            if step % 5 == 0:
                print(f"  step {step + 1}/{total_steps} epoch {epoch + 1} lr {lr:.2e} loss {loss}", flush=True)
            step += 1
        val_loss = mean_loss(tc.forward(val_data, "cross_entropy").result().metrics)
        history.append({"epoch_end": epoch, "val_loss": val_loss})
        print(f"epoch {epoch + 1} done, validation loss {val_loss}", flush=True)

    sampler = tc.save_weights_for_sampler(args.name).result()
    RUNS.mkdir(exist_ok=True)
    run = {"name": args.name, "base_model": args.base, "rank": args.rank, "epochs": args.epochs, "batch": args.batch,
           "lr": args.lr, "train_examples": len(train_data), "val_examples": len(val_data), "tokens_per_epoch": tokens,
           "sampler_path": sampler.path, "seconds": round(time.time() - started), "history": history}
    (RUNS / f"{args.name}.json").write_text(json.dumps(run, indent=2) + "\n")
    print(f"\nsaved sampler weights: {sampler.path}\nrun info: ml/tinker/runs/{args.name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
