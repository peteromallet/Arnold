// Sequence-component static validator.
//
// Static rules:
//   - `exports.default = …` is required.
//   - No `import` / `export` statements (we run via Sucrase + new Function).
//   - `Date.now()`, `performance.now()`, `crypto.getRandomValues()` forbidden
//     so renders stay deterministic per frame.
//   - `Math.random()` only inside `React.useMemo(() => …, [])`.
//
// Param-coverage rule:
//   - For every `params.X` (or `params['X']`) member access in the code,
//     `X` must be present in schema.properties AND in defaults.
//   - The walker handles literal, destructured `{params}`, and aliased
//     `({ params: p })` parameter names — anything that ultimately binds
//     a function parameter to the `params` slot.
//
// Implementation: Sucrase strips JSX/TS first (because the input may use
// either), then we parse the JS output with acorn loaded from esm.sh. If
// either dependency fails to load in the deploy bundle (e.g. cold-start
// network failure), we fall back to a regex scan of `params.X` so the
// determinism + structural checks still run, just with weaker handling
// of destructured/aliased binders.

import { transform as sucraseTransform } from 'https://esm.sh/sucrase@3.34.0?target=denonext';
import * as acorn from 'https://esm.sh/acorn@8.12.1?target=denonext';

interface AcornNode {
  type: string;
  [key: string]: unknown;
}

const PARAMS_REFERENCE = /\bparams(?:\.|\["?)([A-Za-z_$][\w$]*)/g;

function collectParamReferencesRegex(code: string): Set<string> {
  const refs = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = PARAMS_REFERENCE.exec(code)) !== null) {
    if (match[1]) refs.add(match[1]);
  }
  return refs;
}

function walk(node: AcornNode | null | undefined, visit: (n: AcornNode) => void): void {
  if (!node || typeof node !== 'object' || typeof node.type !== 'string') return;
  visit(node);
  for (const key of Object.keys(node)) {
    if (key === 'type' || key === 'loc' || key === 'start' || key === 'end' || key === 'range') {
      continue;
    }
    const value = node[key];
    if (Array.isArray(value)) {
      for (const child of value) {
        walk(child as AcornNode, visit);
      }
    } else if (value && typeof value === 'object') {
      walk(value as AcornNode, visit);
    }
  }
}

/**
 * Collect the local binding names that resolve to the `params` slot of any
 * function parameter list. Examples:
 *   function C(props) { props.params.X }            → binders: ['props']
 *   function C({ params }) { params.X }             → binders: ['params']
 *   function C({ params: p }) { p.X }               → binders: ['p']
 *   const C = ({ params: alias }) => { alias.X };   → binders: ['alias']
 *
 * The first form is special: when the function has a single non-destructured
 * parameter `props`, only `props.params.X` references count, NOT `props.X`.
 * Track that in `propsLikeBinders` separately.
 */
interface ParamBinders {
  /** Names that directly hold the params object. */
  paramsBinders: Set<string>;
  /** Names that hold the whole props object; access via `<name>.params.X`. */
  propsLikeBinders: Set<string>;
}

function collectParamBinders(ast: AcornNode): ParamBinders {
  const paramsBinders = new Set<string>();
  const propsLikeBinders = new Set<string>();

  function inspectFunctionParams(params: AcornNode[] | undefined): void {
    if (!params) return;
    for (const param of params) {
      if (!param) continue;
      if (param.type === 'Identifier') {
        // function C(props) — `props.params.X` is the access pattern
        propsLikeBinders.add(param.name as string);
      } else if (param.type === 'ObjectPattern') {
        // function C({ params }) or function C({ params: alias })
        const properties = param.properties as AcornNode[] | undefined;
        if (!properties) continue;
        for (const prop of properties) {
          if (!prop || prop.type !== 'Property') continue;
          const key = prop.key as AcornNode | undefined;
          const value = prop.value as AcornNode | undefined;
          if (!key || !value) continue;
          const keyName = key.type === 'Identifier' ? (key.name as string) : null;
          if (keyName !== 'params') continue;
          if (value.type === 'Identifier') {
            paramsBinders.add(value.name as string);
          }
          // Nested destructuring like `{ params: { X } }` is unusual — fall
          // through to the regex pass for those edge cases.
        }
      }
      // AssignmentPattern (default values): unwrap left-hand side.
      if (param.type === 'AssignmentPattern' && param.left) {
        inspectFunctionParams([param.left as AcornNode]);
      }
    }
  }

  walk(ast, (node) => {
    if (
      node.type === 'FunctionDeclaration' ||
      node.type === 'FunctionExpression' ||
      node.type === 'ArrowFunctionExpression'
    ) {
      inspectFunctionParams(node.params as AcornNode[] | undefined);
    }
  });

  return { paramsBinders, propsLikeBinders };
}

function memberPropertyName(node: AcornNode): string | null {
  if (!node) return null;
  const property = node.property as AcornNode | undefined;
  if (!property) return null;
  if (node.computed === true) {
    if (property.type === 'Literal' && typeof property.value === 'string') {
      return property.value;
    }
    return null;
  }
  return property.type === 'Identifier' ? (property.name as string) : null;
}

interface AstAnalysis {
  paramNames: Set<string>;
  /** Math.random() call sites NOT contained in a React.useMemo(…) call. */
  illegalMathRandom: boolean;
  /** True iff the AST path ran (vs. regex fallback). */
  usedAst: boolean;
}

function isMathRandomCall(node: AcornNode): boolean {
  if (node.type !== 'CallExpression') return false;
  const callee = node.callee as AcornNode | undefined;
  if (!callee || callee.type !== 'MemberExpression') return false;
  const object = callee.object as AcornNode | undefined;
  if (!object || object.type !== 'Identifier' || object.name !== 'Math') return false;
  const property = callee.property as AcornNode | undefined;
  return property?.type === 'Identifier' && property.name === 'random';
}

function isReactUseMemoCall(node: AcornNode): boolean {
  if (node.type !== 'CallExpression') return false;
  const callee = node.callee as AcornNode | undefined;
  if (!callee) return false;
  // Match React.useMemo(...) (the templates require exactly this form).
  if (callee.type !== 'MemberExpression') return false;
  const object = callee.object as AcornNode | undefined;
  const property = callee.property as AcornNode | undefined;
  if (!object || object.type !== 'Identifier' || object.name !== 'React') return false;
  return property?.type === 'Identifier' && property.name === 'useMemo';
}

function walkWithAncestors(
  root: AcornNode,
  visit: (node: AcornNode, ancestors: AcornNode[]) => void,
): void {
  function recurse(node: AcornNode | null | undefined, ancestors: AcornNode[]): void {
    if (!node || typeof node !== 'object' || typeof node.type !== 'string') return;
    visit(node, ancestors);
    const nextAncestors = ancestors.concat(node);
    for (const key of Object.keys(node)) {
      if (key === 'type' || key === 'loc' || key === 'start' || key === 'end' || key === 'range') {
        continue;
      }
      const value = node[key];
      if (Array.isArray(value)) {
        for (const child of value) recurse(child as AcornNode, nextAncestors);
      } else if (value && typeof value === 'object') {
        recurse(value as AcornNode, nextAncestors);
      }
    }
  }
  recurse(root, []);
}

function analyzeCodeAst(code: string): AstAnalysis {
  let jsCode = code;
  try {
    const transformed = sucraseTransform(code, {
      transforms: ['jsx', 'typescript'],
      jsxRuntime: 'classic',
      production: true,
    });
    jsCode = transformed.code;
  } catch {
    // Sucrase couldn't parse; fall back to regex coverage + the regex strip
    // pattern lifted from ai-generate-effect/templates.ts:482-484.
    const codeWithoutMemos = code.replace(/React\.useMemo\([^)]*Math\.random\(\)[^)]*\)/g, '');
    return {
      paramNames: collectParamReferencesRegex(code),
      illegalMathRandom: /\bMath\.random\s*\(/.test(codeWithoutMemos),
      usedAst: false,
    };
  }

  let ast: AcornNode;
  try {
    ast = acorn.parse(jsCode, {
      ecmaVersion: 'latest',
      sourceType: 'script',
      allowReturnOutsideFunction: true,
    }) as unknown as AcornNode;
  } catch {
    const codeWithoutMemos = code.replace(/React\.useMemo\([^)]*Math\.random\(\)[^)]*\)/g, '');
    return {
      paramNames: collectParamReferencesRegex(code),
      illegalMathRandom: /\bMath\.random\s*\(/.test(codeWithoutMemos),
      usedAst: false,
    };
  }

  const { paramsBinders, propsLikeBinders } = collectParamBinders(ast);
  const paramNames = new Set<string>();
  let illegalMathRandom = false;

  walkWithAncestors(ast, (node, ancestors) => {
    if (node.type === 'MemberExpression') {
      const object = node.object as AcornNode | undefined;
      if (!object) return;

      // Case A: <paramsBinder>.X — direct params binding.
      if (object.type === 'Identifier' && paramsBinders.has(object.name as string)) {
        const name = memberPropertyName(node);
        if (name) paramNames.add(name);
        return;
      }

      // Case B: <propsLikeBinder>.params.X — props.params.X access.
      if (
        object.type === 'MemberExpression' &&
        (object.object as AcornNode | undefined)?.type === 'Identifier' &&
        propsLikeBinders.has(((object.object as AcornNode).name as string)) &&
        memberPropertyName(object) === 'params'
      ) {
        const name = memberPropertyName(node);
        if (name) paramNames.add(name);
      }
      return;
    }

    if (isMathRandomCall(node)) {
      // Allow Math.random only when an ancestor in the chain is a
      // React.useMemo() CallExpression. (The strip-pattern regex from
      // templates.ts:482-484 fails on realistic forms with inner parens
      // — the AST check is precise.)
      const inUseMemo = ancestors.some((ancestor) => isReactUseMemoCall(ancestor));
      if (!inUseMemo) illegalMathRandom = true;
    }
  });

  return { paramNames, illegalMathRandom, usedAst: true };
}

function assertObjectHasKey(obj: object, key: string, label: string, paramName: string): void {
  if (!Object.prototype.hasOwnProperty.call(obj, key)) {
    throw new Error(`Param "${paramName}" used in code but missing from ${label}`);
  }
}

export function validateSequenceComponentCode(
  code: string,
  schema: object,
  defaults: object,
): void {
  if (!code.trim()) {
    throw new Error('Sequence component generation returned empty code');
  }

  if (!code.includes('exports.default')) {
    throw new Error(
      'Generated sequence component must assign the component with exports.default = ComponentName',
    );
  }

  if (/\bimport\s.+from\s/m.test(code) || /^\s*import\s/m.test(code)) {
    throw new Error('Generated sequence component must not include import statements');
  }

  if (/^\s*export\s/m.test(code)) {
    throw new Error(
      'Generated sequence component must not include export statements (use exports.default = …)',
    );
  }

  if (/\bDate\.now\s*\(/.test(code)) {
    throw new Error(
      'Generated sequence component must not call Date.now() — renders must be deterministic per frame',
    );
  }

  if (/\bperformance\.now\s*\(/.test(code)) {
    throw new Error(
      'Generated sequence component must not call performance.now() — renders must be deterministic per frame',
    );
  }

  if (/\bcrypto\.getRandomValues\s*\(/.test(code)) {
    throw new Error(
      'Generated sequence component must not call crypto.getRandomValues() — renders must be deterministic per frame',
    );
  }

  // Single AST pass collects param references AND verifies Math.random()
  // calls are inside React.useMemo(...). On parse failure we fall back to
  // the regex-based strip pattern from ai-generate-effect/templates.ts:482-484.
  const analysis = analyzeCodeAst(code);

  if (analysis.illegalMathRandom) {
    throw new Error(
      'Generated sequence component must not use Math.random() outside React.useMemo — use deterministic math based on frame number instead',
    );
  }

  // Param-coverage check: every params.X must appear in schema.properties AND defaults.
  const schemaProperties = (schema as { properties?: Record<string, unknown> }).properties ?? {};
  for (const paramName of analysis.paramNames) {
    assertObjectHasKey(schemaProperties as object, paramName, 'schema.properties', paramName);
    assertObjectHasKey(defaults, paramName, 'defaults', paramName);
  }
}
