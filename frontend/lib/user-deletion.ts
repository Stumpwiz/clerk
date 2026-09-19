interface DeletionTarget {
    id: number;
    email: string;
    display_name: string;
    is_active: boolean;
}

/** UI guidance only: the API independently checks current identity and state. */
export async function deleteUserWithConfirmation(
    target: DeletionTarget,
    currentUserId: number,
    confirmDelete: (message: string) => boolean,
    sendDelete: (id: number) => Promise<void>,
): Promise<boolean> {
    if (target.id === currentUserId) {
        throw new Error('You cannot delete your own account.');
    }
    if (target.is_active) {
        throw new Error('This user must first be made inactive before deletion.');
    }
    if (!confirmDelete(`Permanently delete ${target.display_name} (${target.email})? This cannot be undone.`)) {
        return false;
    }
    await sendDelete(target.id);
    return true;
}
