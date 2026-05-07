"""CheckpointStore: save and load training state by generation."""

from __future__ import annotations

from pathlib import Path

import torch

from table_peak.training.checkpoint import CheckpointStore, FileCheckpointStore
from table_peak.training.policy_net import PolicyValueNet


def test_file_checkpoint_store_satisfies_protocol(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    assert isinstance(store, CheckpointStore)


def test_save_then_load_roundtrips_net_and_optimizer_state(tmp_path: Path) -> None:
    torch.manual_seed(0)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    # Take a synthetic step so the optimizer has nontrivial state.
    x = torch.zeros((1, 27))
    logits, _ = net(x)
    logits.sum().backward()
    opt.step()

    store = FileCheckpointStore(tmp_path)
    store.save(gen=42, net=net, optimizer=opt, step=100)

    fresh_net = PolicyValueNet()
    fresh_opt = torch.optim.Adam(fresh_net.parameters(), lr=1e-3)
    step = store.load(gen=42, net=fresh_net, optimizer=fresh_opt)

    assert step == 100
    for p_orig, p_loaded in zip(net.parameters(), fresh_net.parameters(), strict=True):
        assert torch.equal(p_orig, p_loaded)


def test_list_generations_returns_sorted_unique_ints(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for gen in (5, 1, 10, 1):  # duplicate 1 => overwrite, not a duplicate listing
        store.save(gen=gen, net=net, optimizer=opt, step=0)

    assert store.list_generations() == [1, 5, 10]


def test_save_creates_missing_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deeper" / "still_deeper"
    store = FileCheckpointStore(nested)
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)

    store.save(gen=0, net=net, optimizer=opt, step=0)

    assert (nested / "gen_0000.pt").exists()
