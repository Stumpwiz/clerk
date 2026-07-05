'use client';

import {useState, useEffect} from 'react';
import {Loader2, Mail, Calendar, User as UserIcon, Plus, Edit2, KeyRound} from 'lucide-react';
import {Modal} from '@/components/modal';
import {Toast} from '@/components/toast';

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? '';

interface LocalUser {
    id: number;
    email: string;
    display_name: string;
    avatar_path: string | null;
    is_active: boolean;
    last_login_at: string | null;
    created_at: string;
    updated_at: string;
}

interface AddUserFormData {
    email: string;
    displayName: string;
    password: string;
    confirmPassword: string;
    isActive: boolean;
}

interface EditUserFormData {
    displayName: string;
    isActive: boolean;
}

interface ResetPasswordFormData {
    newPassword: string;
    confirmPassword: string;
}

const emptyAddUserForm: AddUserFormData = {
    email: '',
    displayName: '',
    password: '',
    confirmPassword: '',
    isActive: true,
};

function getApiErrorMessage(errorBody: unknown, fallback: string) {
    if (
        errorBody &&
        typeof errorBody === 'object' &&
        'detail' in errorBody
    ) {
        const detail = (errorBody as {detail: unknown}).detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail) && detail.length > 0) {
            const firstError = detail[0] as {msg?: unknown};
            if (typeof firstError.msg === 'string') return firstError.msg;
        }
    }
    return fallback;
}

export default function UsersPage() {
    const [users, setUsers] = useState<LocalUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [addUserForm, setAddUserForm] = useState<AddUserFormData>(emptyAddUserForm);
    const [formError, setFormError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [editingUser, setEditingUser] = useState<LocalUser | null>(null);
    const [editUserForm, setEditUserForm] = useState<EditUserFormData>({
        displayName: '',
        isActive: true,
    });
    const [editFormError, setEditFormError] = useState<string | null>(null);
    const [editSubmitting, setEditSubmitting] = useState(false);
    const [isResetModalOpen, setIsResetModalOpen] = useState(false);
    const [resetUser, setResetUser] = useState<LocalUser | null>(null);
    const [resetPasswordForm, setResetPasswordForm] = useState<ResetPasswordFormData>({
        newPassword: '',
        confirmPassword: '',
    });
    const [resetFormError, setResetFormError] = useState<string | null>(null);
    const [resetSubmitting, setResetSubmitting] = useState(false);
    const [toast, setToast] = useState<{
        message: string;
        type: 'success' | 'error';
    } | null>(null);

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            setLoading(true);
            setError(null);

            const response = await fetch(`${API_BASE_URL}/api/users/list`, {
                credentials: 'include',
            });

            if (!response.ok) {
                throw new Error('Failed to fetch users');
            }

            const data = await response.json();
            setUsers(data);
        } catch (error) {
            console.error('Error loading users:', error);
            setError('Failed to load users. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const openAddModal = () => {
        setAddUserForm(emptyAddUserForm);
        setFormError(null);
        setIsAddModalOpen(true);
    };

    const closeAddModal = () => {
        setIsAddModalOpen(false);
        setFormError(null);
    };

    const openEditModal = (user: LocalUser) => {
        setEditingUser(user);
        setEditUserForm({
            displayName: user.display_name,
            isActive: user.is_active,
        });
        setEditFormError(null);
        setIsEditModalOpen(true);
    };

    const closeEditModal = () => {
        setIsEditModalOpen(false);
        setEditingUser(null);
        setEditFormError(null);
    };

    const openResetModal = (user: LocalUser) => {
        setResetUser(user);
        setResetPasswordForm({
            newPassword: '',
            confirmPassword: '',
        });
        setResetFormError(null);
        setIsResetModalOpen(true);
    };

    const closeResetModal = () => {
        setIsResetModalOpen(false);
        setResetUser(null);
        setResetPasswordForm({
            newPassword: '',
            confirmPassword: '',
        });
        setResetFormError(null);
    };

    const validateAddUserForm = () => {
        const trimmedEmail = addUserForm.email.trim();
        const trimmedDisplayName = addUserForm.displayName.trim();

        if (!trimmedEmail || !trimmedDisplayName || !addUserForm.password || !addUserForm.confirmPassword) {
            return 'Email, display name, password, and confirm password are required.';
        }

        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
            return 'Enter a valid email address.';
        }

        if (addUserForm.password !== addUserForm.confirmPassword) {
            return 'Passwords do not match.';
        }

        return null;
    };

    const handleAddUser = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setFormError(null);

        const validationError = validateAddUserForm();
        if (validationError) {
            setFormError(validationError);
            return;
        }

        try {
            setSubmitting(true);
            const response = await fetch(`${API_BASE_URL}/api/users`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: addUserForm.email.trim(),
                    display_name: addUserForm.displayName.trim(),
                    password: addUserForm.password,
                    is_active: addUserForm.isActive,
                }),
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);
                throw new Error(getApiErrorMessage(errorBody, 'Failed to create user'));
            }

            closeAddModal();
            setToast({message: 'User created successfully!', type: 'success'});
            await loadUsers();
        } catch (error) {
            setFormError(error instanceof Error ? error.message : 'Failed to create user');
        } finally {
            setSubmitting(false);
        }
    };

    const handleEditUser = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setEditFormError(null);

        const trimmedDisplayName = editUserForm.displayName.trim();
        if (!trimmedDisplayName) {
            setEditFormError('Display name is required.');
            return;
        }

        if (!editingUser) {
            setEditFormError('No user selected.');
            return;
        }

        try {
            setEditSubmitting(true);
            const response = await fetch(`${API_BASE_URL}/api/users/${editingUser.id}`, {
                method: 'PUT',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    display_name: trimmedDisplayName,
                    is_active: editUserForm.isActive,
                }),
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);
                throw new Error(getApiErrorMessage(errorBody, 'Failed to update user'));
            }

            closeEditModal();
            setToast({message: 'User updated successfully!', type: 'success'});
            await loadUsers();
        } catch (error) {
            setEditFormError(error instanceof Error ? error.message : 'Failed to update user');
        } finally {
            setEditSubmitting(false);
        }
    };

    const handleResetPassword = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setResetFormError(null);

        if (!resetUser) {
            setResetFormError('No user selected.');
            return;
        }

        if (!resetPasswordForm.newPassword || !resetPasswordForm.confirmPassword) {
            setResetFormError('New password and confirm password are required.');
            return;
        }

        if (resetPasswordForm.newPassword.length < 8) {
            setResetFormError('New password must be at least 8 characters.');
            return;
        }

        if (resetPasswordForm.newPassword !== resetPasswordForm.confirmPassword) {
            setResetFormError('Passwords do not match.');
            return;
        }

        try {
            setResetSubmitting(true);
            const response = await fetch(`${API_BASE_URL}/api/users/${resetUser.id}/reset-password`, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    new_password: resetPasswordForm.newPassword,
                }),
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);
                throw new Error(getApiErrorMessage(errorBody, 'Failed to reset password'));
            }

            closeResetModal();
            setToast({message: 'Password reset successfully!', type: 'success'});
        } catch (error) {
            setResetFormError(error instanceof Error ? error.message : 'Failed to reset password');
        } finally {
            setResetSubmitting(false);
        }
    };

    const formatDate = (timestamp: string | null) => {
        if (!timestamp) return 'Never';
        return new Date(timestamp).toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600"/>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900">User Management</h1>
                    <p className="mt-2 text-sm text-gray-600">
                        View local application users
                    </p>
                </div>
                <button
                    type="button"
                    onClick={openAddModal}
                    className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                    <Plus className="w-4 h-4 mr-2"/>
                    Add User
                </button>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                    <p className="text-sm text-red-700">{error}</p>
                </div>
            )}

            <div className="bg-white shadow rounded-lg overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200">
                    <h2 className="text-xl font-semibold text-gray-900">
                        All Users ({users.length})
                    </h2>
                </div>

                {users.length === 0 ? (
                    <div className="p-6 text-center text-gray-500">
                        No users found.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    User
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Email
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Joined
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Last Login
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Status
                                </th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                            {users.map((user) => (
                                <tr key={user.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center">
                                            {user.avatar_path ? (
                                                <img
                                                    src={user.avatar_path}
                                                    alt=""
                                                    className="h-10 w-10 rounded-full"
                                                />
                                            ) : (
                                                <div
                                                    className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                                                    <UserIcon className="h-6 w-6 text-blue-600"/>
                                                </div>
                                            )}
                                            <div className="ml-4">
                                                <div className="text-sm font-medium text-gray-900">
                                                    {user.display_name}
                                                </div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="flex items-center text-sm text-gray-900">
                                            <Mail className="h-4 w-4 mr-2 text-gray-400"/>
                                            {user.email}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        <div className="flex items-center">
                                            <Calendar className="h-4 w-4 mr-2 text-gray-400"/>
                                            {formatDate(user.created_at)}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {formatDate(user.last_login_at)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {user.is_active ? 'Active' : 'Inactive'}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <div className="inline-flex items-center gap-3">
                                            <button
                                                type="button"
                                                onClick={() => openEditModal(user)}
                                                className="text-blue-600 hover:text-blue-900"
                                                title="Edit user"
                                            >
                                                <Edit2 className="w-4 h-4 inline"/>
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => openResetModal(user)}
                                                className="text-blue-600 hover:text-blue-900"
                                                title="Reset password"
                                            >
                                                <KeyRound className="w-4 h-4 inline"/>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            <Modal
                isOpen={isAddModalOpen}
                onClose={closeAddModal}
                title="Add User"
            >
                <form onSubmit={handleAddUser}>
                    {formError && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                            {formError}
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label htmlFor="add-user-email" className="block text-sm font-medium text-gray-700 mb-1">
                                Email *
                            </label>
                            <input
                                type="email"
                                id="add-user-email"
                                value={addUserForm.email}
                                onChange={(event) => setAddUserForm({...addUserForm, email: event.target.value})}
                                autoComplete="email"
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="add-user-display-name" className="block text-sm font-medium text-gray-700 mb-1">
                                Display Name *
                            </label>
                            <input
                                type="text"
                                id="add-user-display-name"
                                value={addUserForm.displayName}
                                onChange={(event) => setAddUserForm({...addUserForm, displayName: event.target.value})}
                                autoComplete="name"
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="add-user-password" className="block text-sm font-medium text-gray-700 mb-1">
                                Password *
                            </label>
                            <input
                                type="password"
                                id="add-user-password"
                                value={addUserForm.password}
                                onChange={(event) => setAddUserForm({...addUserForm, password: event.target.value})}
                                autoComplete="new-password"
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="add-user-confirm-password" className="block text-sm font-medium text-gray-700 mb-1">
                                Confirm Password *
                            </label>
                            <input
                                type="password"
                                id="add-user-confirm-password"
                                value={addUserForm.confirmPassword}
                                onChange={(event) => setAddUserForm({...addUserForm, confirmPassword: event.target.value})}
                                autoComplete="new-password"
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                required
                            />
                        </div>

                        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                            <input
                                type="checkbox"
                                checked={addUserForm.isActive}
                                onChange={(event) => setAddUserForm({...addUserForm, isActive: event.target.checked})}
                                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                            Active
                        </label>
                    </div>

                    <div className="mt-6 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={closeAddModal}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                            disabled={submitting}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                            disabled={submitting}
                        >
                            {submitting ? 'Creating...' : 'Create User'}
                        </button>
                    </div>
                </form>
            </Modal>

            <Modal
                isOpen={isEditModalOpen}
                onClose={closeEditModal}
                title="Edit User"
            >
                <form onSubmit={handleEditUser}>
                    {editFormError && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                            {editFormError}
                        </div>
                    )}

                    {editingUser && (
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Email
                                </label>
                                <div className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-sm text-gray-700">
                                    {editingUser.email}
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Last Login
                                </label>
                                <div className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-sm text-gray-700">
                                    {formatDate(editingUser.last_login_at)}
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Created
                                </label>
                                <div className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-sm text-gray-700">
                                    {formatDate(editingUser.created_at)}
                                </div>
                            </div>

                            <div>
                                <label htmlFor="edit-user-display-name" className="block text-sm font-medium text-gray-700 mb-1">
                                    Display Name *
                                </label>
                                <input
                                    type="text"
                                    id="edit-user-display-name"
                                    value={editUserForm.displayName}
                                    onChange={(event) => setEditUserForm({...editUserForm, displayName: event.target.value})}
                                    autoComplete="name"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                    required
                                />
                            </div>

                            <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                                <input
                                    type="checkbox"
                                    checked={editUserForm.isActive}
                                    onChange={(event) => setEditUserForm({...editUserForm, isActive: event.target.checked})}
                                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                                Active
                            </label>
                        </div>
                    )}

                    <div className="mt-6 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={closeEditModal}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                            disabled={editSubmitting}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                            disabled={editSubmitting}
                        >
                            {editSubmitting ? 'Saving...' : 'Save'}
                        </button>
                    </div>
                </form>
            </Modal>

            <Modal
                isOpen={isResetModalOpen}
                onClose={closeResetModal}
                title="Reset Password"
            >
                <form onSubmit={handleResetPassword}>
                    {resetFormError && (
                        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                            {resetFormError}
                        </div>
                    )}

                    {resetUser && (
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    User
                                </label>
                                <div className="w-full px-3 py-2 border border-gray-200 rounded-md bg-gray-50 text-sm text-gray-700">
                                    {resetUser.display_name} ({resetUser.email})
                                </div>
                            </div>

                            <div>
                                <label htmlFor="reset-user-password" className="block text-sm font-medium text-gray-700 mb-1">
                                    New Password *
                                </label>
                                <input
                                    type="password"
                                    id="reset-user-password"
                                    value={resetPasswordForm.newPassword}
                                    onChange={(event) => setResetPasswordForm({...resetPasswordForm, newPassword: event.target.value})}
                                    autoComplete="new-password"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                    required
                                />
                            </div>

                            <div>
                                <label htmlFor="reset-user-confirm-password" className="block text-sm font-medium text-gray-700 mb-1">
                                    Confirm Password *
                                </label>
                                <input
                                    type="password"
                                    id="reset-user-confirm-password"
                                    value={resetPasswordForm.confirmPassword}
                                    onChange={(event) => setResetPasswordForm({...resetPasswordForm, confirmPassword: event.target.value})}
                                    autoComplete="new-password"
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                                    required
                                />
                            </div>
                        </div>
                    )}

                    <div className="mt-6 flex justify-end gap-3">
                        <button
                            type="button"
                            onClick={closeResetModal}
                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                            disabled={resetSubmitting}
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                            disabled={resetSubmitting}
                        >
                            {resetSubmitting ? 'Resetting...' : 'Reset Password'}
                        </button>
                    </div>
                </form>
            </Modal>

            {toast && (
                <Toast
                    message={toast.message}
                    type={toast.type}
                    onClose={() => setToast(null)}
                />
            )}
        </div>
    );
}
