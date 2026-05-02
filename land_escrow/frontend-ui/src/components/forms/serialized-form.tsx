import React from 'react';
import type { ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Upload } from 'lucide-react';
import type { FormField, SerializedForm } from '../../types.js';
import { Button } from '../ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card.js';
import { Input } from '../ui/input.js';
import { Textarea } from '../ui/textarea.js';
import { cn } from '../../lib/utils.js';

interface FormRendererProps {
  form: SerializedForm;
  csrfToken?: string;
  className?: string;
  submitVariant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'accent' | 'danger';
  extraTop?: ReactNode;
  extraBottom?: ReactNode;
}

function HiddenFields({ fields }: { fields?: Array<{ name: string; value: string }> }) {
  if (!fields?.length) return null;
  return (
    <>
      {fields.map((field) => (
        <input key={field.name} type="hidden" name={field.name} value={field.value} />
      ))}
    </>
  );
}

function RenderField({ field }: { field: FormField }) {
  if (field.type === 'hidden') {
    return <input type="hidden" name={field.name} value={field.value || ''} />;
  }

  const fieldErrors = field.errors || [];
  const id = field.name.replace(/[^a-zA-Z0-9_-]/g, '_');
  const wrapperClass = field.type === 'checkbox' ? 'flex items-start gap-3' : 'space-y-2';

  return (
    <div className={wrapperClass}>
      {field.type !== 'checkbox' ? (
        <label htmlFor={id} className="block text-sm font-semibold text-foreground">
          {field.label}
          {field.required ? <span className="ml-1 text-rose-600">*</span> : null}
        </label>
      ) : null}

      <div className="min-w-0 flex-1">
        {field.type === 'textarea' ? (
          <Textarea
            id={id}
            name={field.name}
            defaultValue={field.value}
            placeholder={field.placeholder}
            required={field.required}
            disabled={field.disabled}
            rows={field.rows || 4}
            className="bg-white/95"
          />
        ) : field.type === 'select' ? (
          <select
            id={id}
            name={field.name}
            defaultValue={field.value}
            required={field.required}
            disabled={field.disabled}
            className="flex h-11 w-full rounded-2xl border border-input bg-white/95 px-4 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <option value="">Select...</option>
            {(field.options || []).map((option) => (
              <option key={`${field.name}-${option.value}`} value={option.value} disabled={option.disabled}>
                {option.label}
              </option>
            ))}
          </select>
        ) : field.type === 'radio' ? (
          <div className="grid gap-2">
            {(field.options || []).map((option) => (
              <label
                key={`${field.name}-${option.value}`}
                className={cn(
                  'flex cursor-pointer items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm transition-colors',
                  option.selected ? 'border-primary bg-primary/5' : 'border-border bg-white/80 hover:bg-muted'
                )}
              >
                <span className="font-semibold text-foreground">{option.label}</span>
                <input
                  type="radio"
                  name={field.name}
                  value={option.value}
                  defaultChecked={option.selected}
                  disabled={field.disabled || option.disabled}
                  className="h-4 w-4 accent-emerald-600"
                />
              </label>
            ))}
          </div>
        ) : field.type === 'checkbox' ? (
          <label className="flex items-start gap-3 rounded-2xl border border-border bg-white/80 px-4 py-3">
            <input
              id={id}
              type="checkbox"
              name={field.name}
              defaultChecked={field.checked}
              disabled={field.disabled}
              className="mt-1 h-4 w-4 accent-emerald-600"
            />
            <span className="text-sm text-foreground">
              <span className="block font-semibold">{field.label}</span>
              {field.helpText ? <span className="mt-1 block text-muted-foreground">{field.helpText}</span> : null}
            </span>
          </label>
        ) : field.type === 'file' ? (
          <Input
            id={id}
            name={field.name}
            type="file"
            accept={field.accept}
            required={field.required}
            disabled={field.disabled}
            className="bg-white/95"
          />
        ) : (
          <Input
            id={id}
            name={field.name}
            type={field.type}
            defaultValue={field.value}
            placeholder={field.placeholder}
            required={field.required}
            disabled={field.disabled}
            min={field.min}
            max={field.max}
            step={field.step}
            autoFocus={field.autoFocus}
            className="bg-white/95"
          />
        )}

        {field.type !== 'checkbox' && field.helpText ? (
          <p className="mt-2 text-xs leading-6 text-muted-foreground">{field.helpText}</p>
        ) : null}

        {fieldErrors.length ? (
          <div className="mt-2 space-y-1">
            {fieldErrors.map((error) => (
              <div key={error} className="flex items-start gap-2 text-sm text-rose-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function FormRenderer({ form, csrfToken, className, submitVariant = 'default', extraTop, extraBottom }: FormRendererProps) {
  const hasSections = !!form.sections?.length;
  const hasRows = !!form.formsetRows?.length;
  const fields = form.fields || [];

  return (
    <div className={cn('space-y-6', className)}>
      {extraTop}

      {form.intro ? (
        <Card className="bg-white/90">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-1 h-5 w-5 text-emerald-700" />
              <p className="text-sm leading-7 text-foreground">{form.intro}</p>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {form.errors?.length ? (
        <Card className="border-rose-200 bg-rose-50/70">
          <CardContent className="p-5">
            <div className="space-y-2 text-sm text-rose-800">
              {form.errors.map((error) => (
                <div key={error} className="flex items-start gap-2">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <form method={form.method || 'post'} action={form.action} encType={form.enctype || 'application/x-www-form-urlencoded'} className="space-y-6">
        {csrfToken ? <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} /> : null}
        <HiddenFields fields={form.hiddenFields} />
        <HiddenFields fields={form.managementFields} />

        {hasSections ? (
          <div className="space-y-4">
            {form.sections!.map((section, index) => (
              <Card key={`${section.title || 'section'}-${index}`} className="bg-white/92">
                {(section.title || section.subtitle) ? (
                  <CardHeader className="pb-4">
                    {section.title ? <CardTitle className="text-base">{section.title}</CardTitle> : null}
                    {section.subtitle ? <CardDescription>{section.subtitle}</CardDescription> : null}
                  </CardHeader>
                ) : null}
                <CardContent className="grid gap-4 md:grid-cols-2">
                  {section.fields.map((field) => (
                    <RenderField key={field.name} field={field} />
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}

        {hasRows ? (
          <div className="space-y-4">
            {form.formsetRows!.map((row) => (
              <Card key={row.index} className="bg-white/92">
                <CardHeader className="pb-4">
                  <CardTitle className="text-base">Member {row.index + 1}</CardTitle>
                  <CardDescription>Provide co-buyer details for this joint purchase slot.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  {(row.hiddenFields || []).map((hidden) => (
                    <input key={hidden.name} type="hidden" name={hidden.name} value={hidden.value} />
                  ))}
                  {row.fields.map((field) => (
                    <RenderField key={field.name} field={field} />
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}

        {!hasSections && !hasRows ? (
          <Card className="bg-white/92">
            <CardContent className="grid gap-4 md:grid-cols-2">
              {fields.map((field) => (
                <RenderField key={field.name} field={field} />
              ))}
            </CardContent>
          </Card>
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button type="submit" variant={submitVariant} className="w-full rounded-full sm:w-auto">
            {form.submitLabel}
          </Button>
          {form.cancelHref ? (
            <a href={form.cancelHref} className="inline-flex h-11 items-center justify-center rounded-full border border-border bg-white/80 px-5 text-sm font-semibold text-foreground transition-colors hover:bg-muted">
              {form.cancelLabel || 'Cancel'}
            </a>
          ) : null}
        </div>
      </form>

      {extraBottom}
    </div>
  );
}
