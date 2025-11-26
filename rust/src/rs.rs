// Reed-Solomon encoder/decoder for GF(2^8)
// Systematic encoding: codeword = [data | parity]
// Polynomial convention: coeff[0] is constant term (x^0), coeff[i] is x^i coefficient
// Codeword position mapping: position 0 = highest power of x (first byte = x^(n-1) coefficient)

use crate::gf256::{gf_mul, gf_div, gf_inv, poly_mul, GF};

/// Evaluate polynomial at x in GF(256)
/// poly[0] is the x^0 coefficient, poly[i] is x^i coefficient
fn poly_eval_at(poly: &[u8], x: u8) -> u8 {
    if poly.is_empty() {
        return 0;
    }
    // Horner's method: start from highest degree
    let mut result = 0u8;
    for &coef in poly.iter().rev() {
        result = (gf_mul(result, x)) ^ coef;
    }
    result
}

/// Build generator polynomial for nsym parity symbols
/// g(x) = (x - alpha^0)(x - alpha^1)...(x - alpha^(nsym-1))
pub fn build_generator(nsym: usize) -> Vec<u8> {
    let mut g = vec![1u8];
    for i in 0..nsym {
        let root = GF.exp[i]; // alpha^i
        // Multiply by (x + alpha^i): in GF(2), subtraction = addition
        g = poly_mul(&g, &[root, 1]);
    }
    g
}

/// Systematic RS encode: given k-byte message, produce n-byte codeword
/// codeword = [message | parity]
pub fn encode(message: &[u8], nsym: usize, generator: &[u8]) -> Vec<u8> {
    let k = message.len();
    let n = k + nsym;
    
    // Polynomial long division to find remainder
    // message(x) * x^nsym mod g(x)
    let mut codeword = vec![0u8; n];
    codeword[..k].copy_from_slice(message);
    
    // Synthetic division
    for i in 0..k {
        let coef = codeword[i];
        if coef != 0 {
            for j in 1..=nsym {
                codeword[i + j] ^= gf_mul(generator[nsym - j], coef);
            }
        }
    }
    
    // Restore message in first k positions
    codeword[..k].copy_from_slice(message);
    codeword
}

/// Compute syndromes S_j = r(alpha^j) for j = 0..nsym-1
/// where r(x) is received codeword as polynomial
/// Codeword bytes map to polynomial: codeword[i] is coefficient of x^(n-1-i)
pub fn calc_syndromes(codeword: &[u8], nsym: usize) -> Vec<u8> {
    let n = codeword.len();
    let mut syndromes = vec![0u8; nsym];
    
    for j in 0..nsym {
        let mut s = 0u8;
        // r(x) = sum_{i=0}^{n-1} r_i * x^i where r_i = codeword[n-1-i]
        // r(alpha^j) = sum_{i=0}^{n-1} codeword[n-1-i] * alpha^(j*i)
        for (idx, &byte) in codeword.iter().enumerate() {
            let power = (n - 1 - idx) as usize;
            let alpha_power = GF.exp[(j * power) % 255];
            s ^= gf_mul(byte, alpha_power);
        }
        syndromes[j] = s;
    }
    syndromes
}

/// Check if all syndromes are zero (no errors)
pub fn syndromes_zero(syndromes: &[u8]) -> bool {
    syndromes.iter().all(|&s| s == 0)
}

/// Berlekamp-Massey algorithm to find error locator polynomial sigma(x)
/// sigma(x) = prod_{j} (1 - X_j * x) where X_j = alpha^(position_j)
pub fn berlekamp_massey(syndromes: &[u8]) -> Vec<u8> {
    let n = syndromes.len();
    let mut c = vec![1u8]; // Current error locator
    let mut b = vec![1u8]; // Previous error locator
    let mut l = 0usize;    // Number of errors
    let mut m = 1usize;    // Shift counter
    let mut delta_prev = 1u8;
    
    for r in 0..n {
        // Compute discrepancy
        let mut delta = syndromes[r];
        for i in 1..=l.min(c.len() - 1) {
            delta ^= gf_mul(c[i], syndromes[r - i]);
        }
        
        if delta == 0 {
            m += 1;
        } else if 2 * l <= r {
            // Length change
            let t = c.clone();
            let scale = gf_mul(delta, gf_inv(delta_prev));
            
            // c(x) = c(x) - delta/delta_prev * x^m * b(x)
            while c.len() < b.len() + m {
                c.push(0);
            }
            for (i, &bi) in b.iter().enumerate() {
                c[i + m] ^= gf_mul(scale, bi);
            }
            
            l = r + 1 - l;
            b = t;
            delta_prev = delta;
            m = 1;
        } else {
            // No length change
            let scale = gf_mul(delta, gf_inv(delta_prev));
            while c.len() < b.len() + m {
                c.push(0);
            }
            for (i, &bi) in b.iter().enumerate() {
                c[i + m] ^= gf_mul(scale, bi);
            }
            m += 1;
        }
    }
    
    // Trim trailing zeros
    while c.len() > 1 && c.last() == Some(&0) {
        c.pop();
    }
    
    c
}

/// Chien search: find roots of error locator polynomial
/// sigma(X_j^-1) = 0 means error at position where X_j = alpha^(n-1-pos)
pub fn chien_search(sigma: &[u8], n: usize) -> Vec<usize> {
    let mut positions = Vec::new();
    
    // For each possible position, check if it's an error location
    for pos in 0..n {
        // X_j = alpha^(n-1-pos), so X_j^-1 = alpha^(pos-n+1) = alpha^(pos+256-n) mod 255
        let exp = ((pos as i32) - (n as i32) + 1 + 510) as usize % 255;
        let x_inv = if exp == 0 { 1u8 } else { GF.exp[exp] };
        
        if poly_eval_at(sigma, x_inv) == 0 {
            positions.push(pos);
        }
    }
    positions
}

/// Forney algorithm: compute error magnitudes
pub fn forney(syndromes: &[u8], sigma: &[u8], positions: &[usize], n: usize) -> Vec<u8> {
    let nsym = syndromes.len();
    
    // Omega(x) = S(x) * sigma(x) mod x^nsym
    // S(x) = S_0 + S_1*x + ...
    let mut omega = vec![0u8; nsym];
    for i in 0..nsym {
        for (j, &sj) in sigma.iter().enumerate() {
            if i >= j {
                omega[i] ^= gf_mul(syndromes[i - j], sj);
            }
        }
    }
    
    // Formal derivative: sigma'(x) = sum of odd-indexed terms
    // d/dx (c_i * x^i) = i * c_i * x^(i-1), and in char 2, i is 0 if even
    let mut sigma_prime = vec![0u8; sigma.len()];
    for i in (1..sigma.len()).step_by(2) {
        sigma_prime[i - 1] = sigma[i];
    }
    
    let mut magnitudes = Vec::with_capacity(positions.len());
    for &pos in positions {
        // X_j = alpha^(n-1-pos)
        let x_exp = ((n - 1 - pos) % 255) as usize;
        let x_j = GF.exp[x_exp];
        let x_j_inv = GF.exp[(255 - x_exp) % 255];
        
        let omega_val = poly_eval_at(&omega, x_j_inv);
        let sigma_prime_val = poly_eval_at(&sigma_prime, x_j_inv);
        
        if sigma_prime_val == 0 {
            // This shouldn't happen for valid error patterns
            magnitudes.push(0);
        } else {
            // e_j = X_j * Omega(X_j^-1) / sigma'(X_j^-1)
            magnitudes.push(gf_mul(x_j, gf_div(omega_val, sigma_prime_val)));
        }
    }
    magnitudes
}

/// Decode RS codeword
pub fn decode(codeword: &[u8], nsym: usize) -> Result<(Vec<u8>, Vec<usize>), &'static str> {
    let n = codeword.len();
    if n < nsym {
        return Err("codeword too short");
    }
    let k = n - nsym;
    
    let syndromes = calc_syndromes(codeword, nsym);
    
    if syndromes_zero(&syndromes) {
        return Ok((codeword[..k].to_vec(), vec![]));
    }
    
    let sigma = berlekamp_massey(&syndromes);
    let num_errors = sigma.len() - 1;
    
    if num_errors == 0 {
        return Err("nonzero syndrome but trivial locator");
    }
    if num_errors > nsym / 2 {
        return Err("too many errors");
    }
    
    let positions = chien_search(&sigma, n);
    
    if positions.len() != num_errors {
        return Err("Chien search failed");
    }
    
    let magnitudes = forney(&syndromes, &sigma, &positions, n);
    
    let mut corrected = codeword.to_vec();
    for (&pos, &mag) in positions.iter().zip(magnitudes.iter()) {
        corrected[pos] ^= mag;
    }
    
    // Verify
    let check = calc_syndromes(&corrected, nsym);
    if !syndromes_zero(&check) {
        return Err("verification failed");
    }
    
    Ok((corrected[..k].to_vec(), positions))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_syndrome_zero_for_valid_codeword() {
        let nsym = 4;
        let gen = build_generator(nsym);
        let message = b"Hello";
        let codeword = encode(message, nsym, &gen);
        let syndromes = calc_syndromes(&codeword, nsym);
        assert!(syndromes_zero(&syndromes), "syndromes should be zero for valid codeword: {:?}", syndromes);
    }

    #[test]
    fn test_encode_decode_no_errors() {
        let nsym = 4;
        let gen = build_generator(nsym);
        let message = b"Hello";
        let codeword = encode(message, nsym, &gen);
        
        let (decoded, positions) = decode(&codeword, nsym).unwrap();
        assert_eq!(decoded, message);
        assert!(positions.is_empty());
    }

    #[test]
    fn test_encode_decode_single_error() {
        let nsym = 4;
        let gen = build_generator(nsym);
        let message = b"Hello";
        let mut codeword = encode(message, nsym, &gen);
        
        codeword[2] ^= 0x55;
        
        let (decoded, positions) = decode(&codeword, nsym).unwrap();
        assert_eq!(decoded, message);
        assert_eq!(positions, vec![2]);
    }

    #[test]
    fn test_encode_decode_two_errors() {
        let nsym = 4;
        let gen = build_generator(nsym);
        let message = b"Hello";
        let mut codeword = encode(message, nsym, &gen);
        
        codeword[1] ^= 0x12;
        codeword[4] ^= 0x34;
        
        let (decoded, positions) = decode(&codeword, nsym).unwrap();
        assert_eq!(decoded, message);
        assert!(positions.contains(&1));
        assert!(positions.contains(&4));
    }

    #[test]
    fn test_too_many_errors() {
        let nsym = 4;
        let gen = build_generator(nsym);
        let message = b"Hello";
        let mut codeword = encode(message, nsym, &gen);
        
        codeword[0] ^= 0x11;
        codeword[2] ^= 0x22;
        codeword[4] ^= 0x33;
        
        let result = decode(&codeword, nsym);
        assert!(result.is_err());
    }
}
