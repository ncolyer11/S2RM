import re

def process_string(input_string):
    """
    Processes the input string according to the given rules:

    1.  Extracts digits from the string.
    2.  Multiplies each digit by 64 if followed by 's', and by 64*27 if followed by 'sb'.
    3.  Calculates the sum of the multiplied digits.
    4.  Handles cases where the text following the digit is 's' or 'sb' (case-insensitive).

    Args:
        input_string: The input string to process.

    Returns:
        The sum of the multiplied digits.
    """

    if not input_string:
        return -1

    # This regex allows digits, spaces, and valid 's'/'sb' sequences (case insensitive)
    pattern = r'^(?:\d|\s?|s|sb|\s?)+$'
    
    # Check if input matches the allowed characters pattern
    if not re.fullmatch(pattern, input_string, re.IGNORECASE):
        return -1

    # Check for invalid combinations (e.g., 'ss', 'sss', etc.)
    if 'ss' in input_string or 'sss' in input_string:
        return -1
    
    total = 0
    matches = re.finditer(r"(\d)(sb|s)?", input_string, re.IGNORECASE)

    for match in matches:
        digit = int(match.group(1))
        suffix = match.group(2)

        if suffix:
            if suffix.lower() == 's':
                total += digit * 64
            elif suffix.lower() == 'sb':
                total += digit * 64 * 27
        else:
            total += digit

    return total

# Tests
def test_process_string():
    tests = [
        ("1s 2Sb 3 4S 5sb", 12419),
        ("1 ", 1),
        ("2s", 128),
        ("3sb ", 5184),
        ("1s1s1s", 192),
        ("1sb1sb1sb", 5184), #corrected value
        ("1 2 3", 6),
        ("1S 2sb 3", 3523),
        ("1 2s 3sb", 5313),
        ("", -1),
        ("0s", 0),
        ("0sb", 0),
        ("0", 0),
        ("1a", -1),
        ("1-", -1),
        ("1#", -1),
        ("1 s b", -1),
        ("1 ss", -1),
        ("1 sss", -1),
        ("1s 2b", -1),
        ("1s 2s 3x", -1),
        ("1s 2s 3-", -1),
        ("a1s", -1),
        ("1s a", -1),
    ]

    for input_string, expected in tests:
        result = process_string(input_string)
        if result != expected:
            print(f"Test failed: Input='{input_string}', Expected={expected}, Got={result}")
        else:
            print(True)

test_process_string()