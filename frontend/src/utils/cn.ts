// frontend/src/utils/cn.ts
/** Tiny className combiner — concatenates truthy entries with a space.
 * Avoids pulling in `clsx`/`tailwind-merge` as extra dependencies. */
export const cn = (...inputs: Array<string | false | null | undefined>): string => {
  return inputs.filter(Boolean).join(' ');
};
