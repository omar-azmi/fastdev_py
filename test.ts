import { parse as cliParse } from "https://deno.land/std@0.184.0/flags/mod.ts"

console.debug(Deno.args)
console.debug(cliParse(Deno.args))
