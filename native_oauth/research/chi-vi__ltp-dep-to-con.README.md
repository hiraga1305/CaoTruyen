# ltp-dep-to-con

A Crystal library to construct grammar trees from LTP4 (Language Technology Platform) output (CWS, POS, NER, DEP) for Chinese-to-Vietnamese machine translation tasks.

## Installation

Add this to your application's `shard.yml`:

```yaml
dependencies:
  ltp-dep-to-con:
    github: chi-vi/ltp-dep-to-con
```

## Usage

```crystal
require "ltp-dep-to-con"

# Example LTP4 output tokens (1-based index usually)
# Structure: {id, word, pos, ner, head, deprel}
tokens = [
  {id: 1, word: "我", pos: "r", ner: "O", head: 2, deprel: "SBV"},
  {id: 2, word: "爱", pos: "v", ner: "O", head: 0, deprel: "HED"},
  {id: 3, word: "北京", pos: "ns", ner: "S-Ns", head: 4, deprel: "ATT"},
  {id: 4, word: "天安门", pos: "ns", ner: "S-Ns", head: 2, deprel: "VOB"}
]

# Build the tree
roots = LtpDepToCon.build_tree(tokens)
root = roots.first

# Access properties
puts root.word # => "爱"
puts root.children.first.word # => "我"

# Flatten to get linear sentence
puts root.flatten.map(&.word).join(" ") # => "我 爱 北京 天安门"

# Reordering (e.g., for Vietnamese grammar)
# Example: Swap ATT (Attribute) to after Head
# "Red Flower" (Red -> Flower)
# Assume Red is child, Flower is head.

flower = root # assuming simplified example
red = flower.children.find { |c| c.deprel == "ATT" }

if red
  # Default visual_index is id. Flower id=2, Red id=1.
  # Move Red to after Flower
  red.visual_index = flower.visual_index + 0.5
end

puts flower.flatten.map(&.word).join(" ")
```

## Features

- **Tree Construction**: Builds a traversable object tree from flat dependency parse lists.
- **Reordering**: Supports `visual_index` based reordering for translation adjustments (e.g., SVO -> VSO or modifier reordering).
- **Data Preservation**: Keeps all LTP tags (POS, NER, DEP) on the nodes.
- **Translation Hooks**: `vietnamese_meanings` property available on nodes.

## Contributing

1. Fork it (<https://github.com/chi-vi/ltp-dep-to-con/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request
