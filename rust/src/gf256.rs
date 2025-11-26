// GF(2^8) arithmetic with primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 (0x11d)
// This is the standard polynomial used by most RS implementations including QR codes.

const PRIM_POLY: u16 = 0x11d;

/// Precomputed tables for GF(256) arithmetic
pub struct Gf256Tables {
    pub exp: [u8; 512],  // exp[i] = alpha^i, doubled for convenience
    pub log: [u8; 256],  // log[x] = i where alpha^i = x (log[0] undefined)
}

impl Gf256Tables {
    pub const fn new() -> Self {
        let mut exp = [0u8; 512];
        let mut log = [0u8; 256];

        let mut x: u16 = 1;
        let mut i = 0usize;
        while i < 255 {
            exp[i] = x as u8;
            exp[i + 255] = x as u8; // duplicate for mod-free lookup
            log[x as usize] = i as u8;
            x <<= 1;
            if x & 0x100 != 0 {
                x ^= PRIM_POLY;
            }
            i += 1;
        }
        // exp[255] = 1 (alpha^255 = 1), log[1] already set
        exp[255] = 1;
        exp[510] = 1;
        // log[0] is undefined but set to 0 to avoid issues
        log[0] = 0;

        Self { exp, log }
    }

    #[inline]
    pub fn mul(&self, a: u8, b: u8) -> u8 {
        if a == 0 || b == 0 {
            0
        } else {
            self.exp[(self.log[a as usize] as usize) + (self.log[b as usize] as usize)]
        }
    }

    #[inline]
    pub fn div(&self, a: u8, b: u8) -> u8 {
        if b == 0 {
            panic!("division by zero in GF(256)");
        }
        if a == 0 {
            0
        } else {
            let log_a = self.log[a as usize] as usize;
            let log_b = self.log[b as usize] as usize;
            // (log_a - log_b) mod 255
            let diff = if log_a >= log_b {
                log_a - log_b
            } else {
                255 + log_a - log_b
            };
            self.exp[diff]
        }
    }

    #[inline]
    pub fn inv(&self, a: u8) -> u8 {
        if a == 0 {
            panic!("inverse of zero in GF(256)");
        }
        self.exp[255 - (self.log[a as usize] as usize)]
    }
}

// Global static tables (computed at compile time)
pub static GF: Gf256Tables = Gf256Tables::new();

#[inline]
pub fn gf_mul(a: u8, b: u8) -> u8 {
    GF.mul(a, b)
}

#[inline]
pub fn gf_div(a: u8, b: u8) -> u8 {
    GF.div(a, b)
}

#[inline]
pub fn gf_inv(a: u8) -> u8 {
    GF.inv(a)
}

/// Polynomial multiplication in GF(256)[x]
/// Result degree = deg(p) + deg(q)
pub fn poly_mul(p: &[u8], q: &[u8]) -> Vec<u8> {
    if p.is_empty() || q.is_empty() {
        return vec![];
    }
    let mut result = vec![0u8; p.len() + q.len() - 1];
    for (i, &pi) in p.iter().enumerate() {
        for (j, &qj) in q.iter().enumerate() {
            result[i + j] ^= gf_mul(pi, qj);
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gf_mul_identity() {
        for a in 0u8..=255 {
            assert_eq!(gf_mul(a, 1), a);
            assert_eq!(gf_mul(1, a), a);
            assert_eq!(gf_mul(a, 0), 0);
            assert_eq!(gf_mul(0, a), 0);
        }
    }

    #[test]
    fn test_gf_inv() {
        for a in 1u8..=255 {
            let inv = gf_inv(a);
            assert_eq!(gf_mul(a, inv), 1, "a={} inv={}", a, inv);
        }
    }

    #[test]
    fn test_gf_div() {
        for a in 1u8..=255 {
            for b in 1u8..=255 {
                let q = gf_div(a, b);
                assert_eq!(gf_mul(q, b), a);
            }
        }
    }
}

