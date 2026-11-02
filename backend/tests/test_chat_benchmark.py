"""Test offline 30-question copilot evaluation harness."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base
from app.services.generator import generate_synthetic_dataset
from app.services.evaluation import evaluate_chat_benchmark
from app.routers.detect import run_detectors
from app.schemas import DetectRunRequest


@pytest.fixture(scope="module")
def benchmark_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Generate synthetic dataset for evaluation
    generate_synthetic_dataset(
        db=session,
        seed=1,
        months=12,
        num_resources=300,
        dataset_id="eval-chat-ds"
    )
    # Run detectors so recommendations exist
    run_detectors(req=DetectRunRequest(dataset_id="eval-chat-ds", path="series"), db=session)

    yield session
    session.close()


def test_30_question_eval_harness(benchmark_db):
    """Execute all 30 questions in chat_questions.yaml and verify metrics meet targets."""
    results = evaluate_chat_benchmark(
        db=benchmark_db,
        dataset_id="eval-chat-ds"
    )

    assert results["total_questions"] == 30
    assert results["tool_selection_accuracy"] >= 0.90, f"Tool accuracy low: {results['tool_selection_accuracy']}"
    assert results["faithfulness_pass_rate"] >= 0.90, f"Faithfulness low: {results['faithfulness_pass_rate']}"
    assert results["ground_truth_agreement"] >= 0.90, f"GT agreement low: {results['ground_truth_agreement']}"
    assert results["trick_question_rejection_rate"] == 1.0, f"Trick rejection low: {results['trick_question_rejection_rate']}"
    assert results["targets_met"] is True

