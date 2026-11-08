from scripts.benchmark_stt import word_error_rate


def test_word_error_rate_counts_missing_words_and_ignores_punctuation():
    assert word_error_rate("Take aspirin at eight.", "Take aspirin at eight") == 0
    assert word_error_rate("Take aspirin at eight", "Take aspirin") == 0.5
