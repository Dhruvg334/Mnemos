"use client";

import { motion } from "framer-motion";

export function FadeIn({ children, className = "", delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.2, 0.65, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function FloatCard({ children, className = "" }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.4, ease: [0.2, 0.65, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
