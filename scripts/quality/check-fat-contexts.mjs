import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import ts from 'typescript';

const repoRoot = process.cwd();
const threshold = 10;
const cutoff = 50;
const allowlistPath = path.join(repoRoot, 'scripts/quality/fat-context-allowlist.json');
const allowlist = new Set(JSON.parse(fs.readFileSync(allowlistPath, 'utf8')));

const configPath = ts.findConfigFile(repoRoot, ts.sys.fileExists, 'tsconfig.app.json');
if (!configPath) {
  console.error('Unable to find tsconfig.app.json');
  process.exit(1);
}

const configFile = ts.readConfigFile(configPath, ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(configFile.config, ts.sys, path.dirname(configPath));
const program = ts.createProgram({
  rootNames: parsed.fileNames,
  options: parsed.options,
});
const checker = program.getTypeChecker();
const failures = [];

for (const sourceFile of program.getSourceFiles()) {
  if (sourceFile.isDeclarationFile) {
    continue;
  }
  if (!sourceFile.fileName.startsWith(path.join(repoRoot, 'src'))) {
    continue;
  }

  ts.forEachChild(sourceFile, function visit(node) {
    const createContextCall = getCreateContextCall(node);
    if (
      ts.isVariableDeclaration(node)
      && ts.isIdentifier(node.name)
      && createContextCall
    ) {
      const typeNode = createContextCall.typeArguments?.[0];
      const sampleNode = typeNode ?? createContextCall.arguments[0];
      if (!sampleNode) {
        return;
      }

      const type = typeNode
        ? checker.getTypeFromTypeNode(typeNode)
        : checker.getTypeAtLocation(sampleNode);
      const leafCount = countLeaves(stripNullable(type), checker, new Set());
      const descriptor = `${path.relative(repoRoot, sourceFile.fileName)}::${node.name.text}`;

      if (leafCount > threshold && !allowlist.has(descriptor)) {
        failures.push({
          descriptor,
          leafCount: leafCount >= cutoff ? `${cutoff}+` : String(leafCount),
        });
      }
    }

    ts.forEachChild(node, visit);
  });
}

if (failures.length > 0) {
  console.error(
    [
      `Fat context check failed. Split the declaration or add a documented exemption to ${path.relative(repoRoot, allowlistPath)}.`,
      ...failures.map((failure) => `- ${failure.descriptor} exceeds ${threshold} leaves (${failure.leafCount})`),
    ].join('\n'),
  );
  process.exit(1);
}

console.log('Fat context check passed.');

function countLeaves(type, typeChecker, seen) {
  const normalized = stripNullable(type);
  const key = getTypeKey(normalized);
  if (seen.has(key)) {
    return 1;
  }

  if (isLeafType(normalized, typeChecker)) {
    return 1;
  }

  seen.add(key);
  const properties = typeChecker.getPropertiesOfType(normalized);
  if (properties.length === 0) {
    return 1;
  }

  let total = 0;
  for (const property of properties) {
    const declaration = property.valueDeclaration ?? property.declarations?.[0];
    if (!declaration) {
      total += 1;
    } else {
      const propertyType = typeChecker.getTypeOfSymbolAtLocation(property, declaration);
      total += countLeaves(propertyType, typeChecker, new Set(seen));
    }
    if (total >= cutoff) {
      return cutoff;
    }
  }

  return total;
}

function getTypeKey(type) {
  return [
    String(type.flags),
    String(type.aliasSymbol?.escapedName ?? ''),
    String(type.symbol?.escapedName ?? ''),
  ].join(':');
}

function stripNullable(type) {
  if (!type.isUnion()) {
    return type;
  }

  const nonNullable = type.types.filter(
    (entry) => (entry.flags & (ts.TypeFlags.Null | ts.TypeFlags.Undefined)) === 0,
  );
  if (nonNullable.length === 1) {
    return nonNullable[0];
  }
  return type;
}

function isLeafType(type, typeChecker) {
  if (type.isUnion()) {
    return type.types.every((entry) => isLeafType(entry, typeChecker));
  }
  if (typeChecker.isArrayType(type) || typeChecker.isTupleType(type)) {
    return true;
  }
  if (type.getCallSignatures().length > 0) {
    return true;
  }
  if (
    type.flags & (
      ts.TypeFlags.StringLike
      | ts.TypeFlags.NumberLike
      | ts.TypeFlags.BooleanLike
      | ts.TypeFlags.BigIntLike
      | ts.TypeFlags.EnumLike
      | ts.TypeFlags.ESSymbolLike
      | ts.TypeFlags.Void
      | ts.TypeFlags.Unknown
      | ts.TypeFlags.Any
      | ts.TypeFlags.Never
      | ts.TypeFlags.TypeParameter
    )
  ) {
    return true;
  }

  const declarations = (type.aliasSymbol ?? type.getSymbol())?.declarations ?? [];
  return declarations.some((declaration) => {
    const fileName = declaration.getSourceFile().fileName;
    return fileName.includes('node_modules') || fileName.endsWith('.d.ts');
  });
}

function isCreateContextCall(expression) {
  const unwrapped = unwrapExpression(expression);
  return (
    (ts.isIdentifier(unwrapped) && resolvesToReactCreateContextIdentifier(unwrapped))
    || (
      ts.isPropertyAccessExpression(unwrapped)
      && unwrapped.name.text === 'createContext'
      && resolvesToReactNamespace(unwrapExpression(unwrapped.expression))
    )
  );
}

function getCreateContextCall(node) {
  if (!ts.isVariableDeclaration(node) || !node.initializer) {
    return null;
  }

  return findCreateContextCall(node.initializer);
}

function unwrapExpression(expression) {
  let current = expression;
  while (
    ts.isParenthesizedExpression(current)
    || ts.isAsExpression(current)
    || ts.isSatisfiesExpression(current)
    || ts.isNonNullExpression(current)
  ) {
    current = current.expression;
  }
  return current;
}

function findCreateContextCall(expression) {
  const unwrapped = unwrapExpression(expression);

  if (ts.isCallExpression(unwrapped)) {
    if (isCreateContextCall(unwrapped.expression)) {
      return unwrapped;
    }

    for (const argument of unwrapped.arguments) {
      const nested = findCreateContextCall(argument);
      if (nested) {
        return nested;
      }
    }
  }

  if (ts.isConditionalExpression(unwrapped)) {
    return (
      findCreateContextCall(unwrapped.whenTrue)
      ?? findCreateContextCall(unwrapped.whenFalse)
    );
  }

  return null;
}

function resolvesToReactNamespace(expression) {
  const unwrapped = unwrapExpression(expression);
  if (ts.isIdentifier(unwrapped)) {
    return getResolvedDeclarations(unwrapped).some((declaration) => {
      if (ts.isNamespaceImport(declaration)) {
        const importDeclaration = declaration.parent.parent;
        return (
          ts.isImportDeclaration(importDeclaration)
          && ts.isStringLiteral(importDeclaration.moduleSpecifier)
          && importDeclaration.moduleSpecifier.text === 'react'
        );
      }

      if (ts.isImportClause(declaration)) {
        const importDeclaration = declaration.parent;
        return (
          declaration.name === unwrapped
          && ts.isImportDeclaration(importDeclaration)
          && ts.isStringLiteral(importDeclaration.moduleSpecifier)
          && importDeclaration.moduleSpecifier.text === 'react'
        );
      }

      return false;
    });
  }
  return false;
}

function resolvesToReactCreateContextIdentifier(identifier) {
  return getResolvedDeclarations(identifier).some((declaration) => {
    if (!ts.isImportSpecifier(declaration)) {
      return false;
    }

    const importDeclaration = declaration.parent.parent.parent.parent;
    return (
      ts.isImportDeclaration(importDeclaration)
      && ts.isStringLiteral(importDeclaration.moduleSpecifier)
      && importDeclaration.moduleSpecifier.text === 'react'
      && declaration.propertyName?.text === 'createContext'
    );
  });
}

function getResolvedDeclarations(identifier) {
  const symbol = checker.getSymbolAtLocation(identifier);
  if (!symbol) {
    return [];
  }

  const declarations = [...(symbol.declarations ?? [])];
  if ((symbol.flags & ts.SymbolFlags.Alias) !== 0) {
    const aliasedSymbol = checker.getAliasedSymbol(symbol);
    declarations.push(...(aliasedSymbol.declarations ?? []));
  }
  return declarations;
}
