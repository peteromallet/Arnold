from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

PILOT_TEMPLATES = (
    "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "ready_templates/image/qwen_image_2512.py",
    "ready_templates/video/wan_i2v.py",
    "ready_templates/audio/ace_step_1_5_t2a_song.py",
    "ready_templates/edit/qwen_image_edit.py",
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.narrate_template", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _generate(template: str, out_path: Path) -> str:
    proc = _run([template, "--mode", "restructure", "--out", str(out_path)])
    assert proc.returncode == 0, proc.stderr
    return out_path.read_text()


def _verify(original: str, generated: Path) -> dict[str, object]:
    proc = _run(["--verify", original, str(generated), "--json"])
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(proc.stdout)
    assert data["status"] == "ok"
    checks = data["checks"]
    for gate in (
        "api_dict_parity",
        "unbound_inputs_parity",
        "register_input_preservation",
        "params_wiring_check",
    ):
        assert checks[gate]["pass"] is True
    return data


def _module_from_path(path: Path):
    module_name = f"_v231_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_inputs_block(source: str) -> str:
    match = re.search(r"PUBLIC_INPUTS = \{(?P<body>.*?)\n\}\n\nOUTPUT_PREFIX", source, re.S)
    assert match is not None
    return match.group("body")


def _assert_no_inline_long_public_defaults(source: str) -> None:
    block = _public_inputs_block(source)
    for line in block.splitlines():
        if "InputSpec(" not in line or "default=" not in line:
            continue
        default_part = line.split("default=", 1)[1].split(", type=", 1)[0]
        if default_part.startswith(("_", "PUBLIC_INPUTS")):
            continue
        literal = default_part.strip()
        if literal[:1] in {"'", '"'}:
            assert len(literal.strip("'\"")) <= 100


def _assert_ready_requirements_is_empty(source: str) -> None:
    match = re.search(r"READY_REQUIREMENTS: dict\[str, object\] = \{\n(?P<body>.*?)\}", source, re.S)
    assert match is not None
    assert "'models'" not in match.group("body")


def test_v231_generated_pilots_cover_polish_contracts(tmp_path: Path) -> None:
    generated: dict[str, str] = {}
    generated_paths: dict[str, Path] = {}

    for template in PILOT_TEMPLATES:
        out_path = tmp_path / Path(template).name
        source = _generate(template, out_path)
        generated[template] = source
        generated_paths[template] = out_path

        assert "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node" in source
        assert "wf = new_workflow(READY_METADATA, source_path=__file__)" in source
        assert ("def " + chr(95) + "node(") not in source
        assert "node(wf," in source
        assert "EDIT_GUIDE =" not in source
        assert "READY_METADATA = ReadyMetadata.build(" in source
        assert "READY_REQUIREMENTS: dict[str, object] = {" in source
        _assert_ready_requirements_is_empty(source)
        assert "output_node=" in source
        assert "output_kind=" not in source

        assert "param_on_" not in source
        assert "emptyacestep1_5latentaudio" not in source
        assert "textencodeacestepaudio1_5" not in source
        assert "conditioning_zero_out_47" not in source
        assert "vaedecode_audio" not in source
        assert "save_audio_m_p3_59" not in source
        assert "text_encode_qwen_image_edit_1" not in source
        assert "text_encode_qwen_image_edit_2" not in source
        _assert_no_inline_long_public_defaults(source)

        banner_lines = [line for line in source.splitlines() if line.strip().startswith("# ════")]
        assert len(banner_lines) == len(set(banner_lines))
        branch_comments = [line for line in source.splitlines() if "BRANCH SELECTION:" in line]
        assert len(branch_comments) == len(set(branch_comments))

        _verify(template, out_path)

        second_path = tmp_path / f"twice_{Path(template).name}"
        second = _generate(str(out_path), second_path)
        assert second == source

        module = _module_from_path(out_path)
        wf = module.build()
        assert wf.outputs

    ltx = generated["ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py"]
    assert "'length': InputSpec(" in ltx
    assert "'frames'" in ltx.split("'length': InputSpec(", 1)[1].split("),", 1)[0]
    assert "'guide_strength': InputSpec(" in ltx
    assert "aliases=('strength',)" in ltx
    assert "'control_video': InputSpec(" in ltx
    assert "clip_name1=MODELS['gemma_clip'].filename" in ltx
    assert "PUBLIC_INPUTS['control_mode'].default" in ltx

    wan = generated["ready_templates/video/wan_i2v.py"]
    assert "'start_image': InputSpec(" in wan
    assert "aliases=('input_image', 'image')" in wan
    assert "'length': InputSpec(" in wan
    assert re.search(r"decoded_frames = node\(wf, ['\"]VAEDecode['\"]", wan)
    assert "decoded_image =" not in wan

    ace = generated["ready_templates/audio/ace_step_1_5_t2a_song.py"]
    assert "'seed_2': InputSpec(" in ace
    assert "aliases=('noise_seed',)" in ace
    assert re.search(r"empty_audio_latent = node\(wf, ['\"]EmptyAceStep1\.5LatentAudio['\"]", ace)
    assert re.search(r"positive_conditioning = node\(wf, ['\"]TextEncodeAceStepAudio1\.5['\"]", ace)
    assert re.search(r"negative_conditioning = node\(wf, ['\"]ConditioningZeroOut['\"]", ace)
    assert re.search(r"decoded_audio = node\(wf, ['\"]VAEDecodeAudio['\"]", ace)
    assert re.search(r"save_audio = node\(wf, ['\"]SaveAudioMP3['\"]", ace)

    edit = generated["ready_templates/edit/qwen_image_edit.py"]
    assert "'source_image': InputSpec(" in edit
    assert "aliases=('input_image', 'image')" in edit
    assert re.search(r"lora_steps = node\(wf, ['\"]PrimitiveInt['\"]", edit)
    assert re.search(r"lora_cfg = node\(wf, ['\"]PrimitiveFloat['\"]", edit)
    assert re.search(r"base_steps = node\(wf, ['\"]PrimitiveInt['\"]", edit)
    assert re.search(r"base_cfg = node\(wf, ['\"]PrimitiveFloat['\"]", edit)
    assert re.search(r"positive_edit_conditioning = node\(wf, ['\"]TextEncodeQwenImageEdit['\"]", edit)
    assert re.search(r"negative_edit_conditioning = node\(wf, ['\"]TextEncodeQwenImageEdit['\"]", edit)
    assert "parity-preserved leaf: wiring into edit encoding changes source API links." in edit
