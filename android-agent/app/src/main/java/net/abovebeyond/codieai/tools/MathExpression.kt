package net.abovebeyond.codieai.tools

import kotlin.math.*

object MathExpression {
    fun evaluate(expression: String): Double {
        val parser = Parser(expression)
        val value = parser.parseExpression()
        parser.skipWhitespace()
        require(parser.isAtEnd()) {
            "Unexpected input at position " + parser.position()
        }
        require(value.isFinite()) { "Result is not finite" }
        return value
    }

    private class Parser(private val source: String) {
        private var index = 0

        fun position(): Int = index
        fun isAtEnd(): Boolean = index >= source.length

        fun skipWhitespace() {
            while (index < source.length && source[index].isWhitespace()) index++
        }

        fun parseExpression(): Double {
            var value = parseTerm()
            while (true) {
                skipWhitespace()
                when {
                    match('+') -> value += parseTerm()
                    match('-') -> value -= parseTerm()
                    else -> return value
                }
            }
        }

        private fun parseTerm(): Double {
            var value = parsePower()
            while (true) {
                skipWhitespace()
                when {
                    match('*') -> value *= parsePower()
                    match('/') -> {
                        val divisor = parsePower()
                        require(divisor != 0.0) { "Division by zero" }
                        value /= divisor
                    }
                    match('%') -> {
                        val divisor = parsePower()
                        require(divisor != 0.0) { "Modulo by zero" }
                        value %= divisor
                    }
                    else -> return value
                }
            }
        }

        private fun parsePower(): Double {
            var value = parseUnary()
            skipWhitespace()
            if (match('^')) {
                value = value.pow(parsePower())
            }
            return value
        }

        private fun parseUnary(): Double {
            skipWhitespace()
            return when {
                match('+') -> parseUnary()
                match('-') -> -parseUnary()
                else -> parsePrimary()
            }
        }

        private fun parsePrimary(): Double {
            skipWhitespace()

            if (match('(')) {
                val value = parseExpression()
                skipWhitespace()
                require(match(')')) { "Missing closing parenthesis" }
                return value
            }

            if (index < source.length && (source[index].isLetter() || source[index] == '_')) {
                val name = parseIdentifier().lowercase()
                skipWhitespace()
                if (name == "pi") return Math.PI
                if (name == "e") return Math.E

                require(match('(')) { "Function '" + name + "' requires parentheses" }
                val args = ArrayList<Double>()
                skipWhitespace()
                if (!peek(')')) {
                    while (true) {
                        args.add(parseExpression())
                        skipWhitespace()
                        if (match(',')) continue
                        break
                    }
                }
                require(match(')')) { "Missing ')' after function arguments" }
                return call(name, args)
            }

            return parseNumber()
        }

        private fun parseNumber(): Double {
            skipWhitespace()
            val start = index
            var sawDot = false
            var sawExponent = false

            while (index < source.length) {
                val ch = source[index]
                when {
                    ch.isDigit() -> index++
                    ch == '.' && !sawDot && !sawExponent -> {
                        sawDot = true
                        index++
                    }
                    (ch == 'e' || ch == 'E') && !sawExponent -> {
                        sawExponent = true
                        index++
                        if (index < source.length && (source[index] == '+' || source[index] == '-')) {
                            index++
                        }
                    }
                    else -> break
                }
            }

            require(index > start) { "Expected a number at position " + start }
            return source.substring(start, index).toDouble()
        }

        private fun parseIdentifier(): String {
            val start = index
            while (index < source.length &&
                (source[index].isLetterOrDigit() || source[index] == '_')
            ) {
                index++
            }
            return source.substring(start, index)
        }

        private fun call(name: String, args: List<Double>): Double =
            when (name) {
                "sqrt" -> unary(name, args) { sqrt(it) }
                "abs" -> unary(name, args) { abs(it) }
                "sin" -> unary(name, args) { sin(it) }
                "cos" -> unary(name, args) { cos(it) }
                "tan" -> unary(name, args) { tan(it) }
                "asin" -> unary(name, args) { asin(it) }
                "acos" -> unary(name, args) { acos(it) }
                "atan" -> unary(name, args) { atan(it) }
                "ln" -> unary(name, args) { ln(it) }
                "log10", "log" -> unary(name, args) { log10(it) }
                "exp" -> unary(name, args) { exp(it) }
                "floor" -> unary(name, args) { floor(it) }
                "ceil" -> unary(name, args) { ceil(it) }
                "round" -> unary(name, args) { round(it) }
                "min" -> {
                    require(args.isNotEmpty()) { "min requires at least one argument" }
                    args.minOrNull()!!
                }
                "max" -> {
                    require(args.isNotEmpty()) { "max requires at least one argument" }
                    args.maxOrNull()!!
                }
                "pow" -> {
                    require(args.size == 2) { "pow requires two arguments" }
                    args[0].pow(args[1])
                }
                else -> throw IllegalArgumentException("Unknown function: " + name)
            }

        private fun unary(name: String, args: List<Double>, fn: (Double) -> Double): Double {
            require(args.size == 1) { name + " requires one argument" }
            return fn(args[0])
        }

        private fun match(ch: Char): Boolean {
            skipWhitespace()
            if (index < source.length && source[index] == ch) {
                index++
                return true
            }
            return false
        }

        private fun peek(ch: Char): Boolean {
            skipWhitespace()
            return index < source.length && source[index] == ch
        }
    }
}
