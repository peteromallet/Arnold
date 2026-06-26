/**
 * Project-level extension requirement contracts.
 *
 * These describe extension dependencies declared at the project/document
 * level and are consumed by timeline readers, packaging resolvers, and
 * host-side loader infrastructure.  Ownership lives at the project layer,
 * not in timeline, family registry, or manifest modules.
 *
 * @publicContract
 */

/** Project-level extension requirement entry. */
export interface ProjectExtensionRequirement {
  extensionId: string;
  versionRange?: string;
  referencedContributionIds?: readonly string[];
  /** Known integrity hash if previously installed. */
  integrity?: string;
  /** Dependency posture: degrade gracefully or require. */
  posture?: 'required' | 'optional';
}

/** Container for project-scoped extension requirement metadata. */
export interface ProjectExtensionRequirements {
  requirements: readonly ProjectExtensionRequirement[];
}
