/**
 * Procedural bug example generator.
 * Zero network / LLM calls — 100% frontend combinatorial generation.
 * Guarantees exactly one real, fixable bug per template instance.
 */

// Substitution pools
const FUNCTION_NAMES = {
  arithmetic: ['calculate_total', 'compute_fee', 'combine_scores', 'tally_points', 'calc_balance'],
  loop: ['find_maximum', 'get_largest', 'locate_peak', 'scan_highest', 'find_best'],
  comparison: ['is_eligible', 'meets_threshold', 'has_access', 'passes_check', 'is_qualified'],
  mutable: ['collect_entry', 'register_item', 'add_record', 'store_event', 'append_tag'],
  exception: ['parse_number', 'convert_setting', 'extract_count', 'read_metric', 'parse_weight'],
  indexing: ['get_first_char', 'fetch_initial', 'lead_element', 'extract_head', 'first_symbol'],
  slice: ['take_first_n', 'grab_prefix', 'truncate_list', 'slice_top', 'limit_items'],
  edge_case: ['compute_mean', 'calc_average', 'mean_score', 'average_value', 'find_mean'],
};

const VARIABLE_NAMES = {
  numbers: ['scores', 'values', 'readings', 'metrics', 'data_points'],
  items: ['items', 'records', 'events', 'entries', 'tokens'],
  params: ['score', 'points', 'rating', 'credits', 'measurement'],
  text: ['text', 'payload', 'word', 'token', 'label'],
};

const SAMPLE_WORDS = ['"alpha"', '"beta"', '"gamma"', '"delta"', '"omega"'];
const SAMPLE_STRINGS = [
  { text: '"python"', expected: '"p"', actual: '"y"' },
  { text: '"gemini"', expected: '"g"', actual: '"e"' },
  { text: '"antigravity"', expected: '"a"', actual: '"n"' },
  { text: '"developer"', expected: '"d"', actual: '"e"' },
];

function pickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickRandomNumber(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

// 8 Bug Templates covering distinct categories
const TEMPLATES = [
  // 1. Wrong Arithmetic Operator (subtraction instead of addition)
  {
    category: 'Wrong Arithmetic Operator',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.arithmetic);
      const val1 = pickRandomNumber(10, 30);
      const val2 = pickRandomNumber(5, 15);
      const expected = val1 + val2;
      const actual = val1 - val2;

      if (useTraceback) {
        return {
          category: 'Wrong Arithmetic Operator (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(base_val, bonus_val):
    return base_val - bonus_val

result = ${func}(${val1}, ${val2})
assert result == ${expected}, f"Expected ${expected}, got {result}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 5, in <module>
    assert result == ${expected}, f"Expected ${expected}, got {result}"
AssertionError: Expected ${expected}, got ${actual}`,
        };
      }

      return {
        category: 'Wrong Arithmetic Operator (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(base_val, bonus_val):
    return base_val - bonus_val`,
        test_content: `def test_${func}():
    from snippet import ${func}
    assert ${func}(${val1}, ${val2}) == ${expected}`,
      };
    },
  },

  // 2. Off-by-One Loop Bound
  {
    category: 'Off-by-One Loop Bound',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.loop);
      const arrVar = pickRandom(VARIABLE_NAMES.numbers);
      const v1 = pickRandomNumber(2, 8);
      const v2 = pickRandomNumber(10, 20);
      const v3 = pickRandomNumber(25, 40);
      const v4 = pickRandomNumber(50, 99); // Highest at the very end

      if (useTraceback) {
        return {
          category: 'Off-by-One Loop Bound (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(${arrVar}):
    if not ${arrVar}:
        return None
    peak = ${arrVar}[0]
    # Bug: loop bound stops one element short of the end
    for i in range(1, len(${arrVar}) - 1):
        if ${arrVar}[i] > peak:
            peak = ${arrVar}[i]
    return peak

result = ${func}([${v1}, ${v2}, ${v3}, ${v4}])
assert result == ${v4}, f"Expected ${v4}, got {result}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 11, in <module>
    assert result == ${v4}, f"Expected ${v4}, got {result}"
AssertionError: Expected ${v4}, got ${v3}`,
        };
      }

      return {
        category: 'Off-by-One Loop Bound (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(${arrVar}):
    if not ${arrVar}:
        return None
    peak = ${arrVar}[0]
    # Bug: loop bound stops one element short of the end
    for i in range(1, len(${arrVar}) - 1):
        if ${arrVar}[i] > peak:
            peak = ${arrVar}[i]
    return peak`,
        test_content: `def test_${func}():
    from snippet import ${func}
    assert ${func}([${v1}, ${v2}, ${v3}, ${v4}]) == ${v4}`,
      };
    },
  },

  // 3. Wrong Comparison Operator (inverted inequality)
  {
    category: 'Wrong Comparison Operator',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.comparison);
      const param = pickRandom(VARIABLE_NAMES.params);
      const threshold = pickRandomNumber(50, 75);
      const passing = threshold + 10;
      const failing = threshold - 10;

      if (useTraceback) {
        return {
          category: 'Wrong Comparison Operator (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(${param}):
    # Bug: inverted comparison operator (< instead of >=)
    if ${param} < ${threshold}:
        return True
    return False

status = ${func}(${passing})
assert status is True, f"Expected True for ${passing}, got {status}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 8, in <module>
    assert status is True, f"Expected True for ${passing}, got {status}"
AssertionError: Expected True for ${passing}, got False`,
        };
      }

      return {
        category: 'Wrong Comparison Operator (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(${param}):
    # Bug: inverted comparison operator (< instead of >=)
    if ${param} < ${threshold}:
        return True
    return False`,
        test_content: `def test_${func}():
    from snippet import ${func}
    assert ${func}(${passing}) is True
    assert ${func}(${failing}) is False`,
      };
    },
  },

  // 4. Mutable Default Argument
  {
    category: 'Mutable Default Argument',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.mutable);
      const itemVar = 'entry';
      const listVar = pickRandom(VARIABLE_NAMES.items);
      const str1 = pickRandom(SAMPLE_WORDS);
      let str2 = pickRandom(SAMPLE_WORDS);
      while (str2 === str1) {
        str2 = pickRandom(SAMPLE_WORDS);
      }

      if (useTraceback) {
        return {
          category: 'Mutable Default Argument (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(${itemVar}, ${listVar}=[]):
    # Bug: mutable default list persists across calls
    ${listVar}.append(${itemVar})
    return ${listVar}

first = ${func}(${str1})
second = ${func}(${str2})
assert second == [${str2}], f"Expected [${str2}], got {second}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 8, in <module>
    assert second == [${str2}], f"Expected [${str2}], got {second}"
AssertionError: Expected [${str2}], got [${str1}, ${str2}]`,
        };
      }

      return {
        category: 'Mutable Default Argument (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(${itemVar}, ${listVar}=[]):
    # Bug: mutable default list persists across calls
    ${listVar}.append(${itemVar})
    return ${listVar}`,
        test_content: `def test_${func}():
    from snippet import ${func}
    first = ${func}(${str1})
    second = ${func}(${str2})
    assert first == [${str1}]
    assert second == [${str2}]`,
      };
    },
  },

  // 5. Swallowed Exception
  {
    category: 'Swallowed Exception',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.exception);
      const num = pickRandomNumber(50, 500);

      if (useTraceback) {
        return {
          category: 'Swallowed Exception (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(raw_input):
    try:
        return int(raw_input)
    except Exception:
        # Bug: swallowed exception returns 0 instead of propagating error
        return 0

result = ${func}("invalid_string_data")
if result == 0:
    raise ValueError(f"Failed to parse integer, got {result}")`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 9, in <module>
    raise ValueError(f"Failed to parse integer, got {result}")
ValueError: Failed to parse integer, got 0`,
        };
      }

      return {
        category: 'Swallowed Exception (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(raw_input):
    try:
        return int(raw_input)
    except Exception:
        # Bug: swallowed exception returns 0 instead of propagating error
        return 0`,
        test_content: `import pytest
from snippet import ${func}

def test_${func}():
    assert ${func}("${num}") == ${num}
    with pytest.raises(ValueError):
        ${func}("invalid_string_data")`,
      };
    },
  },

  // 6. Incorrect String/List Index
  {
    category: 'Incorrect String Index',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.indexing);
      const sample = pickRandom(SAMPLE_STRINGS);

      if (useTraceback) {
        return {
          category: 'Incorrect String Index (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(target_str):
    # Bug: returns index 1 instead of index 0
    return target_str[1]

char = ${func}(${sample.text})
assert char == ${sample.expected}, f"Expected ${sample.expected}, got {char}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 5, in <module>
    assert char == ${sample.expected}, f"Expected ${sample.expected}, got {char}"
AssertionError: Expected ${sample.expected}, got ${sample.actual}`,
        };
      }

      return {
        category: 'Incorrect String Index (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(target_str):
    # Bug: returns index 1 instead of index 0
    return target_str[1]`,
        test_content: `def test_${func}():
    from snippet import ${func}
    assert ${func}(${sample.text}) == ${sample.expected}`,
      };
    },
  },

  // 7. Off-by-One in a Range / Slice
  {
    category: 'Off-by-One Slice',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.slice);
      const limit = pickRandomNumber(2, 4);
      const nums = [10, 20, 30, 40, 50];
      const expectedSlice = nums.slice(0, limit);

      if (useTraceback) {
        return {
          category: 'Off-by-One Slice (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(elements, count):
    # Bug: slice stops 1 element short (count - 1 instead of count)
    return elements[:count - 1]

data = [10, 20, 30, 40, 50]
subset = ${func}(data, ${limit})
assert len(subset) == ${limit}, f"Expected length ${limit}, got {len(subset)}"`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 6, in <module>
    assert len(subset) == ${limit}, f"Expected length ${limit}, got {len(subset)}"
AssertionError: Expected length ${limit}, got ${limit - 1}`,
        };
      }

      return {
        category: 'Off-by-One Slice (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(elements, count):
    # Bug: slice stops 1 element short (count - 1 instead of count)
    return elements[:count - 1]`,
        test_content: `def test_${func}():
    from snippet import ${func}
    data = [10, 20, 30, 40, 50]
    assert ${func}(data, ${limit}) == ${JSON.stringify(expectedSlice)}`,
      };
    },
  },

  // 8. Unhandled Edge Case (Empty Input / ZeroDivisionError)
  {
    category: 'Unhandled Edge Case (Empty Input)',
    generate(useTraceback) {
      const func = pickRandom(FUNCTION_NAMES.edge_case);
      const param = pickRandom(VARIABLE_NAMES.numbers);
      const v1 = pickRandomNumber(10, 20);
      const v2 = pickRandomNumber(20, 30);
      const avg = Math.floor((v1 + v2) / 2);

      if (useTraceback) {
        return {
          category: 'Unhandled Edge Case (Traceback)',
          test_type: 'traceback',
          code: `def ${func}(${param}):
    # Bug: raises ZeroDivisionError when input list is empty
    return sum(${param}) / len(${param})

# Trigger bug on empty input:
avg = ${func}([])`,
          test_content: `Traceback (most recent call last):
  File "snippet.py", line 6, in <module>
    avg = ${func}([])
  File "snippet.py", line 3, in ${func}
    return sum(${param}) / len(${param})
ZeroDivisionError: division by zero`,
        };
      }

      return {
        category: 'Unhandled Edge Case (Pytest)',
        test_type: 'pytest',
        code: `def ${func}(${param}):
    # Bug: raises ZeroDivisionError when input list is empty
    return sum(${param}) / len(${param})`,
        test_content: `def test_${func}():
    from snippet import ${func}
    assert ${func}([${v1}, ${v2}]) == ${avg}
    assert ${func}([]) == 0.0`,
      };
    },
  },
];

/**
 * Generate a randomized example guaranteed not to repeat the template at lastTemplateIndex.
 * Alternates/randomizes between pytest and traceback modes.
 *
 * @param {number} lastTemplateIndex
 * @returns {{ example: { category: string, test_type: string, code: string, test_content: string }, templateIndex: number }}
 */
export function generateRandomExample(lastTemplateIndex) {
  let templateIndex;
  do {
    templateIndex = Math.floor(Math.random() * TEMPLATES.length);
  } while (templateIndex === lastTemplateIndex && TEMPLATES.length > 1);

  // Randomly choose mode: 50% pytest, 50% traceback
  const useTraceback = Math.random() < 0.5;
  const example = TEMPLATES[templateIndex].generate(useTraceback);

  return { example, templateIndex };
}

export { TEMPLATES };
