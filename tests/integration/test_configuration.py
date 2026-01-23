import pytest
from pathlib import Path
import yaml
import tempfile
import shutil
from pydantic import ValidationError
from shared.config import load_yaml_config
from optimizer.config.settings import Settings


@pytest.mark.integration
def test_settings_local_yaml_overrides():
    """Test that settings.local.yaml properly overrides settings.yaml"""
    config_dir = Path(__file__).parent.parent.parent / "src" / "optimizer" / "config"
    settings_file = config_dir / "settings.yaml"
    local_settings_file = config_dir / "settings.local.yaml"

    # Create a temporary backup if settings.local.yaml exists
    backup_file = None
    if local_settings_file.exists():
        backup_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml')
        shutil.copy2(local_settings_file, backup_file.name)

    try:
        # Create a test settings.local.yaml with known overrides
        test_overrides = {
            "agents": {
                "cv_analyst": {
                    "model": "test-model-override",
                    "temperature": 0.123
                }
            },
            "rag": {
                "num_results": 999
            }
        }

        with open(local_settings_file, 'w') as f:
            yaml.dump(test_overrides, f)

        # Load config and verify overrides applied
        config = load_yaml_config(config_dir)

        assert config["agents"]["cv_analyst"]["model"] == "test-model-override"
        assert config["agents"]["cv_analyst"]["temperature"] == 0.123
        assert config["rag"]["num_results"] == 999

        # Verify non-overridden values still come from settings.yaml
        with open(settings_file) as f:
            base_config = yaml.safe_load(f)

        assert config["agents"]["job_analyst"]["model"] == base_config["agents"]["job_analyst"]["model"]
        assert config["rag"]["embedding_model"] == base_config["rag"]["embedding_model"]

    finally:
        # Restore original settings.local.yaml if it existed
        if backup_file:
            shutil.copy2(backup_file.name, local_settings_file)
            Path(backup_file.name).unlink()
        elif local_settings_file.exists():
            local_settings_file.unlink()


@pytest.mark.integration
def test_invalid_temperature_raises_validation_error():
    """Test that invalid temperature values raise ValidationError"""
    # Temperature too high
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "gpt-4", "temperature": 3.0}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 5, "chunk_size": 1000, "chunk_overlap": 200},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "temperature" in str(exc_info.value).lower()

    # Temperature too low
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "gpt-4", "temperature": -0.1}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 5, "chunk_size": 1000, "chunk_overlap": 200},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "temperature" in str(exc_info.value).lower()


@pytest.mark.integration
def test_empty_model_name_raises_validation_error():
    """Test that empty model name raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "", "temperature": 0.7}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 5, "chunk_size": 1000, "chunk_overlap": 200},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "model" in str(exc_info.value).lower()


@pytest.mark.integration
def test_invalid_chunk_overlap_raises_validation_error():
    """Test that chunk_overlap >= chunk_size raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "gpt-4", "temperature": 0.7}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 5, "chunk_size": 1000, "chunk_overlap": 1000},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "chunk_overlap" in str(exc_info.value).lower()


@pytest.mark.integration
def test_invalid_num_results_raises_validation_error():
    """Test that num_results <= 0 raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "gpt-4", "temperature": 0.7}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 0, "chunk_size": 1000, "chunk_overlap": 200},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "num_results" in str(exc_info.value).lower()


@pytest.mark.integration
def test_invalid_chunk_size_raises_validation_error():
    """Test that chunk_size < 100 raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            agents={"cv_analyst": {"model": "gpt-4", "temperature": 0.7}},
            rag={"embedding_model": "text-embedding-ada-002", "collection_name": "kb", "num_results": 5, "chunk_size": 50, "chunk_overlap": 10},
            paths={"knowledge_base": "kb", "vector_db": "vdb"}
        )
    assert "chunk_size" in str(exc_info.value).lower()
