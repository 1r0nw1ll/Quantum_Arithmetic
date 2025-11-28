#!/usr/bin/env python3
"""
QA Right Triangle MCP Server
Exposes QA right triangle calculations as MCP tools with E8 alignment
"""

import json
import sys
import math
import os
from typing import Dict, Sequence
import numpy as np

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from qa_graphrag_utils import compute_e8_alignment, compute_harmonic_index
    E8_AVAILABLE = True
except ImportError:
    E8_AVAILABLE = False

class QARightTriangleMCPServer:
    """MCP Server for QA Right Triangle calculations"""

    def __init__(self):
        self.request_id = 0

    def compute_triangle(self, b: float, e: float) -> Dict:
        """
        Compute QA right triangle from base pair (b, e)

        Returns all QA tuple values and right triangle invariants
        """
        # QA tuple construction
        d = b + e
        a = b + 2*e

        # CANONICAL C, F, G (triangle sides - same as triangle computation below)
        # From SVPwiki Law #12:
        C = 2 * d * e      # Base of right triangle
        F = a * b          # Altitude of right triangle
        G = e**2 + d**2    # Hypotenuse of right triangle

        # QA invariants
        J = b * d
        K = d * a
        X = e * d
        W = b * e
        Y = e * a
        Z = b * a

        # Additional QA invariants
        L = b + d + a  # Linear sum
        H = b * e * d  # Harmonic product

        # Verify Pythagorean property: C² + F² = G²
        pythagorean_check = abs(C**2 + F**2 - G**2) < 1e-6

        # Triangle metrics using C (base), F (altitude), G (hypotenuse)
        area = 0.5 * C * F
        perimeter = C + F + G

        # Inradius: r = area / semi-perimeter
        s = perimeter / 2
        r = area / s if s > 0 else 0

        # Circumradius: R = hypotenuse / 2 (for right triangle)
        R = G / 2 if G > 0 else 0

        # E8 Alignment and Harmonic Index
        e8_align = 0.0
        harmonic_index = 0.0
        if E8_AVAILABLE:
            try:
                qa_tuple = (int(b), int(e), int(d), int(a))
                e8_align = float(compute_e8_alignment(qa_tuple, use_full_roots=True))
                harmonic_index = float(compute_harmonic_index(qa_tuple, loss=0.0))
            except Exception:
                # E8 computation failed, use defaults
                pass

        return {
            "qa_tuple": {
                "b": b,
                "e": e,
                "d": d,
                "a": a
            },
            "invariants": {
                "J": J,
                "K": K,
                "X": X,
                "W": W,
                "Y": Y,
                "Z": Z,
                "L": L,
                "H": H,
                "C": C,
                "F": F,
                "G": G
            },
            "triangle": {
                "C_base": C,
                "F_altitude": F,
                "G_hypotenuse": G,
                "area": round(area, 6),
                "perimeter": round(perimeter, 6),
                "inradius": round(r, 6),
                "circumradius": round(R, 6),
                "pythagorean_verified": pythagorean_check
            },
            "modular": {
                "b_mod_9": int(((b - 1) % 9) + 1),  # {1..9} no zero
                "e_mod_9": int(((e - 1) % 9) + 1),
                "d_mod_9": int(((d - 1) % 9) + 1),
                "a_mod_9": int(((a - 1) % 9) + 1),
                "b_mod_24": int(((b - 1) % 24) + 1),  # {1..24} no zero
                "e_mod_24": int(((e - 1) % 24) + 1),
                "d_mod_24": int(((d - 1) % 24) + 1),
                "a_mod_24": int(((a - 1) % 24) + 1),
                "classification": self._classify_tuple(b, e)
            },
            "e8_geometry": {
                "e8_alignment": round(e8_align, 6),
                "harmonic_index": round(harmonic_index, 6),
                "e8_available": E8_AVAILABLE
            },
            "metadata": {
                "fibonacci_like": self._is_fibonacci_like(b, e),
                "lucas_like": self._is_lucas_like(b, e)
            }
        }

    def _classify_tuple(self, b: float, e: float) -> str:
        """Classify QA tuple by orbit family"""
        d = b + e

        # Singularity check
        if b == 9 and e == 9:
            return "Singularity"

        # Check modular orbit classification
        d_mod_24 = d % 24
        if d_mod_24 == 0:
            return "Cosmos-24-cycle"
        elif d % 8 == 0:
            return "Satellite-8-cycle"
        else:
            return f"General-orbit-{d_mod_24}"

    def _is_fibonacci_like(self, b: float, e: float) -> bool:
        """Check if tuple follows Fibonacci pattern (e.g., b=1, e=1)"""
        return (b == 1 and e == 1) or (b == e)

    def _is_lucas_like(self, b: float, e: float) -> bool:
        """Check if tuple follows Lucas pattern (e.g., b=2, e=1)"""
        return (b == 2 and e == 1) or (b == 2 * e)

    def handle_request(self, request: Dict) -> Dict:
        """Handle JSON-RPC request"""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "qa_compute_triangle",
                            "description": "Compute QA right triangle from base pair (b, e). Returns QA tuple (b,e,d,a), all invariants (J,K,X,W,Y,Z,L,H,C,F,G), triangle properties, and modular classification.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "b": {
                                        "type": "number",
                                        "description": "Base parameter b (must be positive)"
                                    },
                                    "e": {
                                        "type": "number",
                                        "description": "Base parameter e (must be positive)"
                                    }
                                },
                                "required": ["b", "e"]
                            }
                        }
                    ]
                }
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name == "qa_compute_triangle":
                try:
                    b = float(arguments["b"])
                    e = float(arguments["e"])

                    if b <= 0 or e <= 0:
                        return {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {
                                "code": -32602,
                                "message": "Invalid params: b and e must be positive"
                            }
                        }

                    result = self.compute_triangle(b, e)

                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"QA Right Triangle computed for (b={b}, e={e})"
                                },
                                {
                                    "type": "json",
                                    "json": result
                                }
                            ]
                        }
                    }
                except KeyError as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": f"Missing required parameter: {str(e)}"
                        }
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32000,
                            "message": f"Computation error: {str(e)}"
                        }
                    }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

    def run(self):
        """Main server loop - stdio transport"""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    server = QARightTriangleMCPServer()
    server.run()
