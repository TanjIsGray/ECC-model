# LPDDR6 Fault Correlation and Error Model

This note distills guidance from the 2025 EE Times article **“LPDDR6 Balances Performance, Power, and Security”** (see [eetimes.com](https://www.eetimes.com/lpddr6-balances-performance-power-and-security/)) together with published 2024 reliability studies by Google and AMD on large cloud clusters. It captures how LPDDR6 structures metadata, why certain error patterns correlate, and how ECC_model parameterizes those observations for simulation.

![LPDDR6 fault correlation diagram](<LPDDR-6 from eeTimes.svg>)

## Metadata Structure and Correlated Faults

The EETimes article explains that metadata is carved out of the 16 data subarrays (which the article wrongly labels as banks, a different concept in DRAM chips).  Each subarray contributes two bytes for a total of 32 bytes which flow on a bus internal to the DRAM.  This subtracts from the amound of data in the DRAM (1/16th of capacity is lost) and requires extra commands to fetch metadata into registers before reading data, and to write back the metadata after data has been written.  The metadata is buffered in special MDR registers internal to the DRAM.  This metadata is not required to be used for round-trip ECC by the host chip, but that is a necessary feature if LPDDR6 is to be used for reliable large memories.

I redrew the diagram to illustrate the relationship between the data, metadata, and various kinds of multi-bit error.  I will go into that in a moment, but first let's take a brief detour to explain the error patterns most often found in DRAM chips.

## About faults, errors, and data

Faults are the problems occuring in the chip.  Errors are observed in data as a result of faults.  Some parts of the data might agree with the fault, so in general errors show a subset of a fault.

Also, this analysis assumes data is random, there is no special consideration for special cases like all-zeros and all-1s.  Most high reliability systems are like to scramble or encrypt bits, and in some cases the DRAMs may do that internally to minimize unbalanced signals, so simple special cases may not be as common as you might think from looking at plaintext.

## Field Data: Fault Rate and Composition

DRAMs are extraordinarily reliable.  Manufacturers do not disclose their fault rates so we must rely upon field studies.  The most recent large-scale study was by Google and AMD in 2023 (DOI: 10.1109/HPCA56546.2023.10071066) for DDR4 chips and showed on the order of **1e2 faults per billion device-hours**. Roughly **90 %** of observed errors were isolated single-bit flips; the remaining **10 %** were multi-bit errors.  Multi-bit events originate from common-mode mechanisms baked into DRAM designs in drivers or structures controlling rows of data cells or sets of sense amplifiers, as well as addressing errors.

## Fault Classes Captured in ECC_model

To reflect LPDDR6 realities while staying tractable, we group faults into five classes:

- **Single-bit / 1 symbol** – Truly random bit flips within a byte.  The most common kind of errors, and correctable by internal SECDED (Hamming) ECC in the LPDDR6 chip.
- **8-bit / 1 symbol** – Faults which affect a row of bits or controls on one half of a sub-array.  Up to 8 bits will be flipped, depending on the data pattern (since the fault will usually force the bits to zero or to one, which may agree or disagree with the data).
- **16-bit / 2 symbols** – Two bytes, one on each side of a sub-array, commonly sharing a word-line driver or column select logic which control how the sense amplifiers are used.
- **32-bit / 4 symbols** – Four bytes, which may occur if pairs of sub-array share control circuits.
- **Other** – Alternates between 8 contiguous bytes (8-aligned) and 5 scattered bytes spanning unrelated sub-arrays. These represent the “everything else” uncorrectable space where LPDDR6 cannot correct the error.

## Compare to the diagram

If you look back at the diagram you can see an indication of how 8-bit, 16-bit, and 32-bit faults could relate to the sub-arrays of the LPDDR6

## Default Probability Distribution

ECC_model encodes probabilities via integer counts that sum to 10 000 and can be overridden with `--dist`. The defaults align with the fi           eld ratios:

| Fault class      | Description                           | Count | Probability |
|------------------|---------------------------------------|-------|-------------|
| single_bit_1sym  | 1 bit in 1 symbol                     | 9000  | 90.0 %      |
| 8bit_1sym        | 1 byte                                | 600   | 6.0 %       |
| 8bit_2sym        | 2 contiguous bytes (2-aligned)        | 200   | 2.0 %       |
| 8bit_4sym        | 4 contiguous bytes (4-aligned)        | 100   | 1.0 %       |
| out_of_model     | ≥5 contiguous or scattered anomalies  | 100   | 1.0 %       |

This mirrors the empirical 90 / 10 split while making a reasonable expectation that the larger errors are less common, something the DRAM vendors may be able to engineer by a combination of minimizing shared elements and giving those elements conservative design rules.

The program allows these defaults to be changed with a command-line parameter.

## The implications for correlated metadata faults

If you look back at the diagram you will notice that the 8-, 16-, and 32-bit fault causes are shown across the sub-array which includes across the metadata.  The metadata will thus share the same faults as the data.  As the carve-out takes 1/16th of the data, this in practice means that 1/16th of data transfers will be using metadata likely to echo the same fault cause as the data.  This means that the encoded data for those transfers is likely to double its error content.  A fault cause affecting 8 bits of data may have an 8-bit echo in the metadata.  This effect may also double-up 16-bit and 32-bit errors.  This makes them more difficult to correct.  If you choose the correlation option on the ECC_model program you will see the number of uncorrectable and silent errors increases and the Reed-Solomon code is not able to correct the errors you might assume it can, because in 1/16th of the cases it may be seeing double the number or errors.

## The implications for sequential multi-burst transfers

This effect also applies to sequential transfers, for example if you want to use a double-burst to represent 64 bytes of data.  A sequential burst is using the same row with just the column changed, which is to say using a different subset of the sense amps for the transfer.  It also will be correlated, but in this case the correlation risk is for 100% of transfers not just 1/16th since the two bursts will both sample all the subarrays and thus likely sample the same faults affecting half-array word lines or larger structures.

Then the metadata correlation is stacked on top of that.

The sequential correlation problem can be avoided by running two banks in parallel with the same commands, where "bank" in this case is used as per the LPDDR6 standard meaning of a separate set of data arrays.  Faults will not be correlated between such parallel 32-bit transfers.  It would be useful for LPDDR6 to optimize a parallel mirrored-command operating mode.

## The use of a 17th subarray to avoid correlation

LPDDR6 includes an internal single-bit ECC mechanism which uses a 17th sub-array to provide 16 ECC bits.  This is exactly the same size as the carve-out for metadata.  If the metadata is being used for ECC, which is by far the most important purpose, then the round-trip ECC provided by the host chip will correct all the single-bit errors with superior reliability, so this 17th subarray could be put to better use as the metadata (round-trip ECC) storage.

![Alternate construction using the hidden and redundant 17th subarray](<LPDDR-6 from eeTimes using internal ECC.svg>)

This not only eliminates correlation for 8-, 16-, and 32-bit errors.  It would also run faster than the current ECC design since separate read-before and write-after operations are not needed.  And it would return the data to full capacity.

It is difficult to see any good reason for LPDDR6 to have adopted a complex, flawed, slower, and lower capacity alternative.  The 17th subarray is already known to everyone, and clearly available.

The only explanation I have heard is "what about if there is an independent single-bit error in combination?".  But in combinations the internal ECC is inhibited so that makes no sense.

A possible explanation is that there is competition for the internal ECC pathway, since making it modal will add a multiplexor, and that may be so.  Still it is a very minimal overhead and much less complexity and performance cost than the metadata register system.

Perhaps the strongest explanation is the desire to make the metadata purpose undefined, but that seems simply failing to meet obligations of the standard.  It is essential for a product like LPDDR6 to have a strong commitment to reliability.  This is a chip that will be used pervasively around the world in perhaps the largest single DRAM category, including devices where safety is paramount.  The ECC arrangements should not be an afterthought, they should be integral to the standard, and the vendors are well aware that the internal single bit ECC is not adequate.  The clear main use case for metadata is ECC.  It is certainly the only use that could justify the complex engineering of the metadata system as found in the spec. Round-trip metadata for host-based ECC should be an explicit goal with its proper support ensured in the JEDEC specification.

The reasons for the weak and costly metadata design in LPDDR6 are a mystery, and quite sad for all of us who could have expected a design with integrity from JEDEC for this very important standard.  A design destined to guide trillions of chips over the next decade deserves better.

## What about multiple errors

You may be wondering why the fault model did not include unbounded errors.  This would include independent combinations like a single bit error from failed refresh or even stuck with a VRT (variable refresh timing) together with a word line failure in a different part of the same transfer.  There is a two part answer to this.

The first is that DRAM is very, very reliable.  Not reliable enough to allow us to avoid correction, but reliable enough that dual independent errors in one 64-byte region will be orders of magnitude rarer than the faults which cause bounded errors, faults which directly flow from necessary structures and circuits in the chip.  We cannot correct everything on LPDDR6, we need to assign resources to fixing the more likely errors.  Dual independent errors are simply down in the noise of rarest errors where our concern must be detection, not correction.

That brings us to the second part of the answer.  If the application requires reliability then using LPDDR6 will require effort.  The host chip should use a competent ECC algorithm.  The algorithm should be tuned for probity - the detection and reliable reporting of uncorrectable errors.  The host should follow best practices like patrolling to correct transient (usually refresh) errors so they cannot accumulate.  The host should retry uncorrectable errors that might relate to burst errors on the wiring, and it should log corrections so that it can recognize repetitions which show permanent or semi-permanent errors and use strategies to replace them in the memory map as well as possibly retesting after a grace period.  The applications that run on LPDDR6 need to have the ability to retry actions in the rare cases where errors cannot be corrected.

LPDDR6 is a design which requires the host chip to lean in to get the best quality results.

## What happens if the host wants metadata other than ECC

The LPDDR6 spec deliberately allows that there may be uses other than ECC, but provides very minimal resources to satisfy this in a reliable way.  Still, it is possible.  A 64-byte data transfer comes with 4 bytes for metadata.  This could be used for single-symbol Reed-Solomon correction, another 8 bits for a CRC, and 8 bits left over for meta-uses.  The host can correct any single-byte error (which is likely about 96% of all errors) and detect uncorrectable errors with aroun 99.9% reliability.  The host could even choose to correct just single bits (about 90% of errors) like the internal ECC would, while leaving 16 bits for non-ECC purposes.

LPDDR6 does not have unlimited resources, and the users will need to make a judgement on what is most important.  For most uses reliability will be essential, and I would argue that if the host needs round-trip ECC then JEDEC is duty-bound to implement that to the best reliability possible, which is by using the 17th subarray for round-trip data.