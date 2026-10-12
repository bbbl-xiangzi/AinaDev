type Category = { id: number; post_permission?: string; allow_post?: boolean; can_post?: boolean };

export function newPostHref(pathname: string): string {
  const match = /^\/c\/([1-9]\d*)\/?$/.exec(pathname);
  return match ? `/new?category_id=${match[1]}` : '/new';
}

export function canPostInCategory(category: Category, role?: string): boolean {
  if (typeof category.can_post === "boolean") return category.can_post;
  const permission = category.post_permission || (category.allow_post ? 'public' : 'closed');
  return permission === 'public' || (permission === 'staff_only' && role === 'super_admin');
}

export function initialPostCategory(categories: Category[], requested: string | null, role?: string): number {
  const id = requested && /^[1-9]\d*$/.test(requested) ? Number(requested) : 0;
  return (categories.find(c => c.id === id && canPostInCategory(c, role))
    || categories.find(c => canPostInCategory(c, role)))?.id || 0;
}
