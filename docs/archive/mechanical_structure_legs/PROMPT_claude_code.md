Read the CLAUDE.md in this directory, then read the MASTER_SPEC at C:\Iora\docs\system\mechanical_structure_legs\MASTER_SPEC_iora_structural_detection.md — particularly Parts 2 (design evolution), 4 (three-source envelope), 7 (existing code assets), 8 (modular build plan), and 9 (hybrid implementation with request.security).

Also read the two existing Pine Script templates:
- C:\Iora\tw_indicators\templates\iora_bos_choch.pine
- C:\Iora\tw_indicators\templates\HTF Candles (M5 - 12MN).pine

Once you've read everything, confirm your understanding of the system, then let's build Phase 1: Module 1 (Hybrid Envelope Engine) as `C:\Iora\tw_indicators\iora_structure\iora_envelope.pine`.

This module should:
- Use request.security with lookahead=barmerge.lookahead_on to get live building candle OHLC for M5, M15, H1, H4, D (and optionally W, MN)
- Store last N-1 closed child candle highs/lows/closes per parent TF (N = natural parent-child ratio: 5 for M5, 3 for M15, 4 for H1, 4 for H4, 6 for D)
- Compute the three-source envelope per parent TF: dynamic_floor (avg lows), dynamic_mid (avg closes), dynamic_ceil (avg highs)
- Compute gradients (deltas from previous values)
- Plot the envelope as step-lines per TF (with enable/disable toggles)
- Show a compact dashboard table with current envelope values and gradient direction per TF
