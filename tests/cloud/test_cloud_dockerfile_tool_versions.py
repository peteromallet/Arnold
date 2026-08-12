from arnold_pipelines.megaplan.cloud.template import _dockerfile_template


def test_cloud_dockerfile_pins_codex_cli_version() -> None:
    dockerfile = _dockerfile_template().template

    assert 'ARG CODEX_VERSION="0.144.3"' in dockerfile
    assert '"@openai/codex@${CODEX_VERSION}"' in dockerfile
    assert 'test "$(codex --version)" = "codex-cli ${CODEX_VERSION}"' in dockerfile
    assert "npm i -g @openai/codex " not in dockerfile
