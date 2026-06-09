import { projectsApi, peopleApi, deliverablesApi, assignmentsApi, budgetsApi, authApi } from '../services/api';

describe('api service structure', () => {
  it('projectsApi exposes CRUD methods', () => {
    expect(typeof projectsApi.getAll).toBe('function');
    expect(typeof projectsApi.getById).toBe('function');
    expect(typeof projectsApi.create).toBe('function');
    expect(typeof projectsApi.update).toBe('function');
    expect(typeof projectsApi.remove).toBe('function');
  });

  it('peopleApi exposes CRUD and allocation methods', () => {
    expect(typeof peopleApi.getAll).toBe('function');
    expect(typeof peopleApi.getById).toBe('function');
    expect(typeof peopleApi.create).toBe('function');
    expect(typeof peopleApi.update).toBe('function');
    expect(typeof peopleApi.remove).toBe('function');
    expect(typeof peopleApi.getAllocation).toBe('function');
  });

  it('assignmentsApi exposes CRUD methods', () => {
    expect(typeof assignmentsApi.getAll).toBe('function');
    expect(typeof assignmentsApi.create).toBe('function');
    expect(typeof assignmentsApi.remove).toBe('function');
  });

  it('deliverablesApi exposes CRUD methods', () => {
    expect(typeof deliverablesApi.getAll).toBe('function');
    expect(typeof deliverablesApi.create).toBe('function');
    expect(typeof deliverablesApi.remove).toBe('function');
  });

  it('budgetsApi exposes CRUD methods', () => {
    expect(typeof budgetsApi.getAll).toBe('function');
    expect(typeof budgetsApi.create).toBe('function');
    expect(typeof budgetsApi.remove).toBe('function');
  });

  it('authApi exposes all auth methods', () => {
    expect(typeof authApi.verify).toBe('function');
    expect(typeof authApi.me).toBe('function');
    expect(typeof authApi.devLogin).toBe('function');
    expect(typeof authApi.getUsers).toBe('function');
    expect(typeof authApi.updateRole).toBe('function');
  });
});
