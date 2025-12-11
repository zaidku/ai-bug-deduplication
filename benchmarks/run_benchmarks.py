"""Performance benchmarking tools."""

import time
import statistics
import json
from typing import Dict, List, Callable
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class BenchmarkResult:
    """Benchmark result data."""

    name: str
    total_iterations: int
    total_duration: float
    avg_duration: float
    min_duration: float
    max_duration: float
    p50_duration: float
    p95_duration: float
    p99_duration: float
    requests_per_second: float
    timestamp: str


class PerformanceBenchmark:
    """Performance benchmarking utility."""

    def __init__(self, name: str):
        self.name = name
        self.durations: List[float] = []
        self.start_time = None
        self.end_time = None

    def run(self, func: Callable, iterations: int = 1000, warmup: int = 100):
        """
        Run benchmark.

        Args:
            func: Function to benchmark
            iterations: Number of iterations
            warmup: Warmup iterations (not counted)
        """
        print(f"Running benchmark: {self.name}")
        print(f"Warmup: {warmup} iterations")

        # Warmup
        for _ in range(warmup):
            func()

        print(f"Benchmark: {iterations} iterations")

        # Actual benchmark
        self.durations = []
        self.start_time = time.time()

        for i in range(iterations):
            start = time.time()
            func()
            duration = time.time() - start
            self.durations.append(duration)

            if (i + 1) % 100 == 0:
                print(f"  Completed: {i + 1}/{iterations}")

        self.end_time = time.time()

        return self.get_results()

    def get_results(self) -> BenchmarkResult:
        """Calculate and return benchmark results."""
        if not self.durations:
            raise ValueError("No benchmark data available")

        sorted_durations = sorted(self.durations)
        total_duration = self.end_time - self.start_time

        return BenchmarkResult(
            name=self.name,
            total_iterations=len(self.durations),
            total_duration=total_duration,
            avg_duration=statistics.mean(self.durations),
            min_duration=min(self.durations),
            max_duration=max(self.durations),
            p50_duration=self._percentile(sorted_durations, 50),
            p95_duration=self._percentile(sorted_durations, 95),
            p99_duration=self._percentile(sorted_durations, 99),
            requests_per_second=len(self.durations) / total_duration,
            timestamp=datetime.utcnow().isoformat(),
        )

    @staticmethod
    def _percentile(sorted_data: List[float], percentile: float) -> float:
        """Calculate percentile value."""
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def print_results(self, result: BenchmarkResult):
        """Print formatted results."""
        print(f"\n{'='*60}")
        print(f"Benchmark Results: {result.name}")
        print(f"{'='*60}")
        print(f"Total Iterations:  {result.total_iterations}")
        print(f"Total Duration:    {result.total_duration:.2f}s")
        print(f"\nLatency:")
        print(f"  Average:         {result.avg_duration*1000:.2f}ms")
        print(f"  Min:             {result.min_duration*1000:.2f}ms")
        print(f"  Max:             {result.max_duration*1000:.2f}ms")
        print(f"  P50 (median):    {result.p50_duration*1000:.2f}ms")
        print(f"  P95:             {result.p95_duration*1000:.2f}ms")
        print(f"  P99:             {result.p99_duration*1000:.2f}ms")
        print(f"\nThroughput:")
        print(f"  Requests/sec:    {result.requests_per_second:.2f}")
        print(f"{'='*60}\n")

    def save_results(self, result: BenchmarkResult, filename: str):
        """Save results to JSON file."""
        with open(filename, "w") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"Results saved to: {filename}")


def benchmark_embedding_generation():
    """Benchmark embedding generation performance."""
    from app.services.embedding_service import EmbeddingService

    service = EmbeddingService()
    test_text = "Login button not responding on mobile Safari browser"

    benchmark = PerformanceBenchmark("Embedding Generation")

    def generate():
        service.generate_embedding(test_text)

    result = benchmark.run(generate, iterations=100, warmup=10)
    benchmark.print_results(result)
    benchmark.save_results(result, "benchmarks/embedding_generation.json")

    return result


def benchmark_vector_search():
    """Benchmark vector similarity search performance."""
    from app.utils.vector_store import VectorStore
    from app.services.embedding_service import EmbeddingService
    import numpy as np

    # Setup
    vector_store = VectorStore()
    embedding_service = EmbeddingService()

    # Add test vectors
    for i in range(1000):
        embedding = np.random.rand(384).tolist()
        vector_store.add_vector(f"test_{i}", embedding)

    # Benchmark search
    query_embedding = embedding_service.generate_embedding("test query")

    benchmark = PerformanceBenchmark("Vector Similarity Search (1000 vectors)")

    def search():
        vector_store.search(query_embedding, k=10)

    result = benchmark.run(search, iterations=1000, warmup=100)
    benchmark.print_results(result)
    benchmark.save_results(result, "benchmarks/vector_search.json")

    return result


def benchmark_quality_check():
    """Benchmark quality checking performance."""
    from app.services.quality_checker import QualityChecker

    checker = QualityChecker(
        min_description_length=20, require_repro_steps=True, require_logs=False
    )

    bug_data = {
        "title": "Login button not responding on mobile",
        "description": "When clicking the login button on iOS Safari, nothing happens. "
        "Expected behavior is successful authentication.",
        "steps_to_reproduce": ["Open app", "Navigate to login", "Click button"],
        "expected_result": "User logged in",
        "actual_result": "No response",
    }

    benchmark = PerformanceBenchmark("Quality Check")

    def check():
        checker.validate_bug(bug_data)

    result = benchmark.run(check, iterations=10000, warmup=1000)
    benchmark.print_results(result)
    benchmark.save_results(result, "benchmarks/quality_check.json")

    return result


def benchmark_duplicate_detection_pipeline():
    """Benchmark full duplicate detection pipeline."""
    from app.services.duplicate_detector import DuplicateDetector
    from app.services.quality_checker import QualityChecker
    from app.services.similarity_engine import SimilarityEngine
    from app.services.embedding_service import EmbeddingService
    from app.utils.vector_store import VectorStore

    # Setup
    embedding_service = EmbeddingService()
    vector_store = VectorStore()
    quality_checker = QualityChecker(
        min_description_length=20, require_repro_steps=False, require_logs=False
    )
    similarity_engine = SimilarityEngine(embedding_service, vector_store)
    detector = DuplicateDetector(
        embedding_service,
        similarity_engine,
        quality_checker,
        vector_store,
        similarity_threshold=0.85,
        low_confidence_threshold=0.70,
    )

    bug_data = {
        "title": "Login button not responding",
        "description": "Button click has no effect on mobile Safari browser",
        "product": "Mobile App",
        "severity": "major",
    }

    benchmark = PerformanceBenchmark("Full Duplicate Detection Pipeline")

    def process():
        detector.process_incoming_bug(bug_data)

    result = benchmark.run(process, iterations=100, warmup=10)
    benchmark.print_results(result)
    benchmark.save_results(result, "benchmarks/duplicate_detection.json")

    return result


if __name__ == "__main__":
    """Run all benchmarks."""
    import os

    # Create benchmarks directory
    os.makedirs("benchmarks", exist_ok=True)

    print("Starting performance benchmarks...\n")

    # Run benchmarks
    results = {
        "embedding_generation": benchmark_embedding_generation(),
        "vector_search": benchmark_vector_search(),
        "quality_check": benchmark_quality_check(),
        "duplicate_detection": benchmark_duplicate_detection_pipeline(),
    }

    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        print(
            f"{name:30s} {result.requests_per_second:>10.2f} req/s  "
            f"(p95: {result.p95_duration*1000:>6.2f}ms)"
        )
    print("=" * 60)
