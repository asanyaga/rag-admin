import React, { useState } from 'react';
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardFooter, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  FileText, 
  ChevronRight, 
  ChevronLeft, 
  Info,
  Check,
  Layers,
  Settings,
  Eye
} from 'lucide-react';

const CreateIndexWireframe = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [previewDocumentId, setPreviewDocumentId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    selectedDocs: [],
    chunkingStrategy: 'recursive',
    chunkSize: 512,
    overlap: 50,
    unit: 'characters',
    embeddingProvider: 'openai',
    embeddingModel: 'text-embedding-3-small'
  });

  // Mock documents
  const documents = [
    { id: '1', name: 'ACPL-IM', uploadedAt: '4 days ago', size: '2.3 MB', pages: 45 },
    { id: '2', name: 'Acorn-I-REIT-OM', uploadedAt: '4 days ago', size: '1.8 MB', pages: 32 }
  ];

  // Mock chunk preview data
  const mockChunks = [
    { id: 1, text: 'This is the first chunk of text from the document. It contains approximately 512 characters depending on the configuration...', tokens: 95 },
    { id: 2, text: 'Second chunk with overlap from previous. The overlap ensures context continuity between chunks for better retrieval...', tokens: 88 },
    { id: 3, text: 'Third chunk continues the document narrative. Real estate investment trusts (REITs) are companies that own and operate...', tokens: 102 },
    { id: 4, text: 'Fourth chunk discussing financial metrics and performance indicators relevant to the REIT sector and investment strategies...', tokens: 91 },
    { id: 5, text: 'Fifth chunk covering risk factors and market conditions that may affect the investment performance and returns...', tokens: 85 },
    { id: 6, text: 'Sixth chunk detailing the management structure and key personnel responsible for strategic decisions and operations...', tokens: 87 },
    { id: 7, text: 'Seventh chunk outlining distribution policies and dividend payment schedules for shareholders and investors...', tokens: 83 },
    { id: 8, text: 'Eighth chunk describing property portfolio composition including geographic distribution and property types...', tokens: 89 },
    { id: 9, text: 'Ninth chunk analyzing market trends and competitive positioning within the real estate investment landscape...', tokens: 90 },
    { id: 10, text: 'Tenth chunk summarizing key investment highlights and value propositions for potential and existing investors...', tokens: 86 }
  ];

  const steps = [
    { number: 1, title: 'Details', icon: FileText },
    { number: 2, title: 'Documents', icon: Layers },
    { number: 3, title: 'Configuration', icon: Settings },
    { number: 4, title: 'Preview', icon: Eye }
  ];

  const handleNext = () => {
    if (currentStep < 4) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const handleDocumentToggle = (docId) => {
    setFormData(prev => ({
      ...prev,
      selectedDocs: prev.selectedDocs.includes(docId)
        ? prev.selectedDocs.filter(id => id !== docId)
        : [...prev.selectedDocs, docId]
    }));
  };

  const canProceedFromStep = (step) => {
    switch(step) {
      case 1: return formData.name.trim() !== '';
      case 2: return formData.selectedDocs.length > 0;
      case 3: return true;
      default: return true;
    }
  };

  const isStepComplete = (step) => {
    if (step < currentStep) return true; // Past steps are complete
    if (step === currentStep) return canProceedFromStep(step); // Current step validity
    return false; // Future steps not complete
  };

  const handleStepClick = (step) => {
    // Only allow clicking on completed steps or the next available step
    if (step < currentStep || (step === currentStep + 1 && canProceedFromStep(currentStep))) {
      setCurrentStep(step);
    } else if (step === currentStep) {
      // Already on this step, do nothing
      return;
    }
  };

  // Set default preview document when entering step 4
  React.useEffect(() => {
    if (currentStep === 4 && formData.selectedDocs.length > 0 && !previewDocumentId) {
      setPreviewDocumentId(formData.selectedDocs[0]);
    }
  }, [currentStep, formData.selectedDocs, previewDocumentId]);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Create Index</h1>
          <p className="text-gray-600 mt-2">
            Configure how your documents will be chunked and embedded for retrieval
          </p>
        </div>

        {/* Step Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => {
              const StepIcon = step.icon;
              const isCompleted = currentStep > step.number;
              const isCurrent = currentStep === step.number;
              const isClickable = isStepComplete(step.number - 1) || step.number <= currentStep;
              
              return (
                <React.Fragment key={step.number}>
                  <div 
                    className={`flex flex-col items-center ${
                      isClickable ? 'cursor-pointer' : 'cursor-not-allowed'
                    }`}
                    onClick={() => isClickable && handleStepClick(step.number)}
                  >
                    <div className={`
                      w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-all
                      ${isCompleted ? 'bg-green-500 text-white' : 
                        isCurrent ? 'bg-blue-500 text-white' : 
                        isClickable ? 'bg-gray-300 text-gray-600 hover:bg-gray-400' :
                        'bg-gray-200 text-gray-400'}
                      ${isClickable && !isCurrent ? 'hover:scale-110' : ''}
                    `}>
                      {isCompleted ? <Check className="w-6 h-6" /> : <StepIcon className="w-6 h-6" />}
                    </div>
                    <span className={`text-sm font-medium ${
                      isCurrent ? 'text-blue-600' : 
                      isClickable ? 'text-gray-700' : 
                      'text-gray-400'
                    }`}>
                      {step.title}
                    </span>
                  </div>
                  {index < steps.length - 1 && (
                    <div className={`flex-1 h-1 mx-4 ${
                      isCompleted ? 'bg-green-500' : 'bg-gray-200'
                    }`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Main Content Card */}
        <Card>
          <CardHeader>
            <CardTitle>{steps[currentStep - 1].title}</CardTitle>
            <CardDescription>
              {currentStep === 1 && "Enter basic information about your index"}
              {currentStep === 2 && "Select documents to include in this index"}
              {currentStep === 3 && "Configure chunking and embedding settings"}
              {currentStep === 4 && "Preview how your documents will be chunked"}
            </CardDescription>
          </CardHeader>

          <CardContent className="min-h-[400px]">
            {/* Step 1: Details */}
            {currentStep === 1 && (
              <div className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="name">
                    Name <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="name"
                    placeholder="My Index"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                  />
                  {formData.name.trim() === '' && (
                    <p className="text-sm text-gray-500">Index name is required</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Optional description..."
                    rows={4}
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                  />
                  <p className="text-sm text-gray-500">
                    Help others understand what this index is for
                  </p>
                </div>
              </div>
            )}

            {/* Step 2: Documents */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-sm text-gray-600">
                    {documents.length} documents available
                  </p>
                  <Badge variant="outline">
                    {formData.selectedDocs.length} selected
                  </Badge>
                </div>

                {formData.selectedDocs.length === 0 && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Select at least one document to create an index
                    </AlertDescription>
                  </Alert>
                )}

                <div className="space-y-3">
                  {documents.map((doc) => (
                    <Card 
                      key={doc.id}
                      className={`cursor-pointer transition-colors hover:bg-gray-50 ${
                        formData.selectedDocs.includes(doc.id) ? 'border-blue-500 bg-blue-50' : ''
                      }`}
                      onClick={() => handleDocumentToggle(doc.id)}
                    >
                      <CardContent className="flex items-center gap-4 p-4">
                        <Checkbox
                          checked={formData.selectedDocs.includes(doc.id)}
                          onCheckedChange={() => handleDocumentToggle(doc.id)}
                        />
                        <FileText className="w-8 h-8 text-gray-400" />
                        <div className="flex-1">
                          <h3 className="font-medium">{doc.name}</h3>
                          <p className="text-sm text-gray-500">
                            {doc.uploadedAt} • {doc.size} • {doc.pages} pages
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Configuration */}
            {currentStep === 3 && (
              <div className="space-y-8">
                {/* Chunking Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold">Chunking</h3>
                    <Badge variant="secondary">Recommended</Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="strategy">Strategy</Label>
                      <Select 
                        value={formData.chunkingStrategy}
                        onValueChange={(value) => setFormData({...formData, chunkingStrategy: value})}
                      >
                        <SelectTrigger id="strategy">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="recursive">Recursive Character (Recommended)</SelectItem>
                          <SelectItem value="character">Character</SelectItem>
                          <SelectItem value="token">Token</SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-gray-500">
                        Splits text recursively by common separators
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="unit">Unit</Label>
                      <Select 
                        value={formData.unit}
                        onValueChange={(value) => setFormData({...formData, unit: value})}
                      >
                        <SelectTrigger id="unit">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="characters">Characters</SelectItem>
                          <SelectItem value="tokens">Tokens</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="chunkSize">Chunk Size</Label>
                      <Input
                        id="chunkSize"
                        type="number"
                        value={formData.chunkSize}
                        onChange={(e) => setFormData({...formData, chunkSize: parseInt(e.target.value)})}
                      />
                      <p className="text-xs text-gray-500">
                        Target size per chunk (100-8000)
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="overlap">Overlap</Label>
                      <Input
                        id="overlap"
                        type="number"
                        value={formData.overlap}
                        onChange={(e) => setFormData({...formData, overlap: parseInt(e.target.value)})}
                      />
                      <p className="text-xs text-gray-500">
                        Overlap between chunks (max 256)
                      </p>
                    </div>
                  </div>

                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Smaller chunks provide more precise retrieval but may increase costs. 
                      512-1024 characters works well for most documents.
                    </AlertDescription>
                  </Alert>
                </div>

                {/* Embedding Section */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Embedding</h3>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="provider">Provider</Label>
                      <Select 
                        value={formData.embeddingProvider}
                        onValueChange={(value) => setFormData({...formData, embeddingProvider: value})}
                      >
                        <SelectTrigger id="provider">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="cohere">Cohere</SelectItem>
                          <SelectItem value="huggingface">HuggingFace</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="model">Model</Label>
                      <Select 
                        value={formData.embeddingModel}
                        onValueChange={(value) => setFormData({...formData, embeddingModel: value})}
                      >
                        <SelectTrigger id="model">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="text-embedding-3-small">
                            text-embedding-3-small (1536 dims)
                          </SelectItem>
                          <SelectItem value="text-embedding-3-large">
                            text-embedding-3-large (3072 dims)
                          </SelectItem>
                          <SelectItem value="text-embedding-ada-002">
                            text-embedding-ada-002 (1536 dims)
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 4: Preview */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="font-medium mb-2">Preview Configuration</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-600">Documents:</span>{' '}
                      <span className="font-medium">{formData.selectedDocs.length}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Strategy:</span>{' '}
                      <span className="font-medium">{formData.chunkingStrategy}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Chunk Size:</span>{' '}
                      <span className="font-medium">{formData.chunkSize} {formData.unit}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Overlap:</span>{' '}
                      <span className="font-medium">{formData.overlap} {formData.unit}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="preview-document">Select Document to Preview</Label>
                    <Badge variant="outline">First 10 chunks</Badge>
                  </div>
                  <Select 
                    value={previewDocumentId || ''}
                    onValueChange={setPreviewDocumentId}
                  >
                    <SelectTrigger id="preview-document">
                      <SelectValue placeholder="Choose a document..." />
                    </SelectTrigger>
                    <SelectContent>
                      {formData.selectedDocs.map((docId) => {
                        const doc = documents.find(d => d.id === docId);
                        return (
                          <SelectItem key={docId} value={docId}>
                            {doc?.name} ({doc?.size} • {doc?.pages} pages)
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-gray-500">
                    Preview how this document will be split into chunks
                  </p>
                </div>

                {previewDocumentId && (
                  <>
                    <div className="border rounded-lg divide-y max-h-96 overflow-y-auto">
                      {mockChunks.map((chunk, index) => (
                        <div key={chunk.id} className="p-4 hover:bg-gray-50">
                          <div className="flex items-start gap-3">
                            <Badge variant="secondary" className="mt-1">
                              {index + 1}
                            </Badge>
                            <div className="flex-1">
                              <p className="text-sm text-gray-700">{chunk.text}</p>
                              <p className="text-xs text-gray-500 mt-2">
                                ~{chunk.tokens} tokens
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <Alert>
                      <Info className="h-4 w-4" />
                      <AlertDescription>
                        Estimated total chunks for {documents.find(d => d.id === previewDocumentId)?.name}: ~{Math.ceil(documents.find(d => d.id === previewDocumentId)?.pages * 500 / formData.chunkSize)} chunks
                        <br />
                        Total for all {formData.selectedDocs.length} document{formData.selectedDocs.length > 1 ? 's' : ''}: ~{formData.selectedDocs.reduce((sum, docId) => {
                          const doc = documents.find(d => d.id === docId);
                          return sum + Math.ceil((doc?.pages || 0) * 500 / formData.chunkSize);
                        }, 0)} chunks
                      </AlertDescription>
                    </Alert>
                  </>
                )}

                {!previewDocumentId && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Select a document above to preview how it will be chunked
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}
          </CardContent>

          <CardFooter className="flex justify-between border-t pt-6">
            <div>
              {currentStep > 1 && (
                <Button variant="outline" onClick={handleBack}>
                  <ChevronLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              )}
            </div>

            <div className="flex gap-2">
              <Button variant="outline">
                Save as Draft
              </Button>
              
              {currentStep < 4 ? (
                <Button 
                  onClick={handleNext}
                  disabled={!canProceedFromStep(currentStep)}
                >
                  Continue
                  <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button className="bg-green-600 hover:bg-green-700">
                  Create & Build Index
                </Button>
              )}
            </div>
          </CardFooter>
        </Card>

        {/* Help Text */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-500">
            Need help? Check out our{' '}
            <a href="#" className="text-blue-600 hover:underline">
              documentation
            </a>{' '}
            or{' '}
            <a href="#" className="text-blue-600 hover:underline">
              watch a tutorial
            </a>
          </p>
        </div>
      </div>
    </div>
  );
};

export default CreateIndexWireframe;
